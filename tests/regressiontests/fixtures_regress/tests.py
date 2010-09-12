# -*- coding: utf-8 -*-
# Unittests for fixtures.
import os
import sys
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from django.core import management
from django.core.management.commands.dumpdata import sort_dependencies
from django.core.management.base import CommandError
from django.db.models import signals
from django.test import TestCase

from models import Animal, Stuff
from models import Absolute, Parent, Child
from models import Article, Widget
from models import Store, Person, Book
from models import NKChild, RefToNKChild
from models import Circle1, Circle2, Circle3
from models import ExternalDependency
from models import animal_pre_save_check
from models import Tagger, Posting, Tag, TaggerTag, PostingTag


class TestFixtures(TestCase):

    def assertRaisesMessage(self, exc, msg, func, *args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception, e:
            self.assertEqual(msg, str(e))
            self.assertTrue(isinstance(e, exc), "Expected %s, got %s" % (exc, type(e)))

    def test_duplicate_pk(self):
        """
        This is a regression test for ticket #3790.
        """
        # Load a fixture that uses PK=1
        management.call_command(
            'loaddata',
            'sequence',
            verbosity=0,
            commit=False
            )

        # Create a new animal. Without a sequence reset, this new object
        # will take a PK of 1 (on Postgres), and the save will fail.

        animal = Animal(
            name='Platypus',
            latin_name='Ornithorhynchus anatinus',
            count=2,
            weight=2.2
            )
        animal.save()
        self.assertEqual(animal.id, 2)

    def test_pretty_print_xml(self):
        """
        Regression test for ticket #4558 -- pretty printing of XML fixtures
        doesn't affect parsing of None values.
        """
        # Load a pretty-printed XML fixture with Nulls.
        management.call_command(
            'loaddata',
            'pretty.xml',
            verbosity=0,
            commit=False
            )
        self.assertEqual(Stuff.objects.all()[0].name, None)
        self.assertEqual(Stuff.objects.all()[0].owner, None)

    def test_absolute_path(self):
        """
        Regression test for ticket #6436 --
        os.path.join will throw away the initial parts of a path if it
        encounters an absolute path.
        This means that if a fixture is specified as an absolute path,
        we need to make sure we don't discover the absolute path in every
        fixture directory.
        """
        load_absolute_path = os.path.join(
            os.path.dirname(__file__),
            'fixtures',
            'absolute.json'
            )
        management.call_command(
            'loaddata',
            load_absolute_path,
            verbosity=0,
            commit=False
            )
        self.assertEqual(Absolute.load_count, 1)

    def test_pg_sequence_resetting_checks(self):
        """
        Test for ticket #7565 -- PostgreSQL sequence resetting checks shouldn't
        ascend to parent models when inheritance is used
        (since they are treated individually).
        """
        management.call_command(
            'loaddata',
            'model-inheritance.json',
            verbosity=0,
            commit=False
            )
        self.assertEqual(Parent.objects.all()[0].id, 1)
        self.assertEqual(Child.objects.all()[0].id, 1)

    def test_nk_deserialize(self):
        """
        Test for ticket #13030
        natural keys deserialize with fk to inheriting model
        """
        management.call_command(
            'loaddata',
            'model-inheritance.json',
            verbosity=0,
            commit=False
            )
        management.call_command(
            'loaddata',
            'nk-inheritance.json',
            verbosity=0,
            commit=False
            )
        self.assertEqual(
            NKChild.objects.get(pk=1).data,
            'apple'
            )

        self.assertEqual(
            RefToNKChild.objects.get(pk=1).nk_fk.data,
            'apple'
            )

    def test_nk_deserialize_xml(self):
        """
        Test for ticket #13030
        natural keys deserialize with fk to inheriting model
        """
        management.call_command(
            'loaddata',
            'model-inheritance.json',
            verbosity=0,
            commit=False
            )
        management.call_command(
            'loaddata',
            'nk-inheritance.json',
            verbosity=0,
            commit=False
            )
        management.call_command(
            'loaddata',
            'nk-inheritance2.xml',
            verbosity=0,
            commit=False
            )
        self.assertEqual(
            NKChild.objects.get(pk=2).data,
            'banana'
            )
        self.assertEqual(
            RefToNKChild.objects.get(pk=2).nk_fk.data,
            'apple'
            )

    def test_mysql_close_connection_after_loaddata(self):
        """
        Test for ticket #7572 -- MySQL has a problem if the same connection is
        used to create tables, load data, and then query over that data.
        To compensate, we close the connection after running loaddata.
        This ensures that a new connection is opened when test queries are
        issued.
        """
        management.call_command(
            'loaddata',
            'big-fixture.json',
            verbosity=0,
            commit=False
            )
        articles = Article.objects.exclude(id=9)
        self.assertEqual(
            articles.values_list('id', flat=True).__repr__(),
            "[1, 2, 3, 4, 5, 6, 7, 8]"
            )
        # Just for good measure, run the same query again.
        # Under the influence of ticket #7572, this will
        # give a different result to the previous call.
        self.assertEqual(
            articles.values_list('id', flat=True).__repr__(),
            "[1, 2, 3, 4, 5, 6, 7, 8]"
            )

    def test_field_value_coerce(self):
        """
        Test for tickets #8298, #9942 - Field values should be coerced into the
        correct type by the deserializer, not as part of the database write.
        """
        sys.stdout = StringIO()
        signals.pre_save.connect(animal_pre_save_check)
        management.call_command(
            'loaddata',
            'animal.xml',
            verbosity=0,
            commit=False
            )
        self.assertEqual(
            sys.stdout.getvalue(),
            "Count = 42 (<type 'int'>)\nWeight = 1.2 (<type 'float'>)\n"
            )
        signals.pre_save.disconnect(animal_pre_save_check)
        sys.stdout = sys.__stdout__

    def test_dumpdata_uses_default_manager(self):
        """
        Regression for #11286
        Ensure that dumpdata honors the default manager
        Dump the current contents of the database as a JSON fixture
        """
        sys.stdout = StringIO()
        management.call_command(
            'loaddata',
            'animal.xml',
            verbosity=0,
            commit=False
            )
        management.call_command(
            'loaddata',
            'sequence.json',
            verbosity=0,
            commit=False
            )
        animal = Animal(
            name='Platypus',
            latin_name='Ornithorhynchus anatinus',
            count=2,
            weight=2.2
            )
        animal.save()
        management.call_command(
            'dumpdata',
            'fixtures_regress.animal',
            format='json',
            )
        self.assertEqual(
            sys.stdout.getvalue(),
            """[{"pk": 1, "model": "fixtures_regress.animal", "fields": {"count": 3, "weight": 1.2, "name": "Lion", "latin_name": "Panthera leo"}}, {"pk": 10, "model": "fixtures_regress.animal", "fields": {"count": 42, "weight": 1.2, "name": "Emu", "latin_name": "Dromaius novaehollandiae"}}, {"pk": 11, "model": "fixtures_regress.animal", "fields": {"count": 2, "weight": 2.2000000000000002, "name": "Platypus", "latin_name": "Ornithorhynchus anatinus"}}]"""
            )
        sys.stdout = sys.__stdout__

    def test_proxy_model_included(self):
        """
        Regression for #11428 - Proxy models aren't included when you dumpdata
        """
        sys.stdout = StringIO()
        # Create an instance of the concrete class
        Widget(name='grommet').save()
        management.call_command(
            'dumpdata',
            'fixtures_regress.widget',
            'fixtures_regress.widgetproxy',
            format='json',
            )
        self.assertEqual(
            sys.stdout.getvalue(),
            """[{"pk": 1, "model": "fixtures_regress.widget", "fields": {"name": "grommet"}}]"""
            )
        sys.stdout = sys.__stdout__

    def test_nk_on_serialize(self):
        """
        Check that natural key requirements are taken into account
        when serializing models
        """
        sys.stdout = StringIO()
        management.call_command(
            'loaddata',
            'forward_ref_lookup.json',
            verbosity=0,
            commit=False
            )
        management.call_command(
            'dumpdata',
            'fixtures_regress.book',
            'fixtures_regress.person',
            'fixtures_regress.store',
            verbosity=0,
            format='json',
            use_natural_keys=True,
            )
        self.assertEqual(
            sys.stdout.getvalue(),
            """[{"pk": 2, "model": "fixtures_regress.store", "fields": {"name": "Amazon"}}, {"pk": 3, "model": "fixtures_regress.store", "fields": {"name": "Borders"}}, {"pk": 4, "model": "fixtures_regress.person", "fields": {"name": "Neal Stephenson"}}, {"pk": 1, "model": "fixtures_regress.book", "fields": {"stores": [["Amazon"], ["Borders"]], "name": "Cryptonomicon", "author": ["Neal Stephenson"]}}]"""
            )
        sys.stdout = sys.__stdout__

    def test_dependency_sorting(self):
        """
        Now lets check the dependency sorting explicitly
        It doesn't matter what order you mention the models
        Store *must* be serialized before then Person, and both
        must be serialized before Book.
        """
        sorted_deps = sort_dependencies(
            [('fixtures_regress', [Book, Person, Store])]
            )
        self.assertEqual(
            sorted_deps,
            [Store, Person, Book]
            )

    def test_dependency_sorting_2(self):
        sorted_deps = sort_dependencies(
            [('fixtures_regress', [Book, Store, Person])]
            )
        self.assertEqual(
            sorted_deps,
            [Store, Person, Book]
            )

    def test_dependency_sorting_3(self):
        sorted_deps = sort_dependencies(
            [('fixtures_regress', [Store, Book, Person])]
            )
        self.assertEqual(
            sorted_deps,
            [Store, Person, Book]
            )

    def test_dependency_sorting_4(self):
        sorted_deps = sort_dependencies(
            [('fixtures_regress', [Store, Person, Book])]
            )
        self.assertEqual(
            sorted_deps,
            [Store, Person, Book]
            )

    def test_dependency_sorting_5(self):
        sorted_deps = sort_dependencies(
            [('fixtures_regress', [Person, Book, Store])]
            )
        self.assertEqual(
            sorted_deps,
            [Store, Person, Book]
            )

    def test_dependency_sorting_6(self):
        sorted_deps = sort_dependencies(
            [('fixtures_regress', [Person, Store, Book])]
            )
        self.assertEqual(
            sorted_deps,
            [Store, Person, Book]
            )

    def test_dependency_sorting_dangling(self):
        sorted_deps = sort_dependencies(
            [('fixtures_regress', [Person, Circle1, Store, Book])]
            )
        self.assertEqual(
            sorted_deps,
            [Circle1, Store, Person, Book]
            )

    def test_dependency_sorting_tight_circular(self):
        self.assertRaisesMessage(
            CommandError,
            """Can't resolve dependencies for fixtures_regress.Circle1, fixtures_regress.Circle2 in serialized app list.""",
            sort_dependencies,
            [('fixtures_regress', [Person, Circle2, Circle1, Store, Book])],
            )

    def test_dependency_sorting_tight_circular_2(self):
        self.assertRaisesMessage(
            CommandError,
            """Can't resolve dependencies for fixtures_regress.Circle1, fixtures_regress.Circle2 in serialized app list.""",
            sort_dependencies,
            [('fixtures_regress', [Circle1, Book, Circle2])],
            )

    def test_dependency_self_referential(self):
        self.assertRaisesMessage(
            CommandError,
            """Can't resolve dependencies for fixtures_regress.Circle3 in serialized app list.""",
            sort_dependencies,
            [('fixtures_regress', [Book, Circle3])],
            )

    def test_dependency_sorting_m2m(self):
        sorted_deps = sort_dependencies(
            [('fixtures_regress', [Tagger, Posting, Tag, TaggerTag, PostingTag])],
            )
        self.assertEqual(
            sorted_deps,
            [Tagger, Posting, Tag, TaggerTag, PostingTag]
            )

    def test_dependency_sorting_long(self):
        self.assertRaisesMessage(
            CommandError,
            """Can't resolve dependencies for fixtures_regress.Circle1, fixtures_regress.Circle2, fixtures_regress.Circle3 in serialized app list.""",
            sort_dependencies,
            [('fixtures_regress', [Person, Circle2, Circle1, Circle3, Store, Book])],
            )

    def test_dependency_sorting_normal(self):
        sorted_deps = sort_dependencies(
            [('fixtures_regress', [Person, ExternalDependency, Book])]
            )
        self.assertEqual(
            sorted_deps,
            [Person, Book, ExternalDependency]
            )

    def test_normal_pk(self):
        """
        Check that normal primary keys still work
        on a model with natural key capabilities
        """
        management.call_command(
            'loaddata',
            'non_natural_1.json',
            verbosity=0,
            commit=False
            )
        management.call_command(
            'loaddata',
            'forward_ref_lookup.json',
            verbosity=0,
            commit=False
            )
        management.call_command(
            'loaddata',
            'non_natural_2.xml',
            verbosity=0,
            commit=False
            )
        books = Book.objects.all()
        self.assertEqual(
            books.__repr__(),
            """[<Book: Cryptonomicon by Neal Stephenson (available at Amazon, Borders)>, <Book: Ender's Game by Orson Scott Card (available at Collins Bookstore)>, <Book: Permutation City by Greg Egan (available at Angus and Robertson)>]"""
            )

    def test_dumpdata_of_dependencies_across_many_to_many(self):
        from datetime import datetime
        tagger = Tagger.objects.create(name='some punk')
        posting = Posting.objects.create(tagger=tagger, time=datetime.now(),
                                         text='Eat your greens.',)
        tag = Tag.objects.create(name='good advice')
        PostingTag.objects.create(posting=posting, tag=tag)
        TaggerTag.objects.create(tagger=tagger, tag=tag)

        management.call_command(
            'dumpdata',
            'fixtures_regress.tagger',
            'fixtures_regress.posting',
            'fixtures_regress.tag',
            'fixtures_regress.taggertag',
            'fixtures_regress.postingtag',
            verbosity=0,
            format='json',
            use_natural_keys=True,
            )

class TestFixtureLoadErrors(TestCase):
    """
    Test for ticket #4371 -- fixture loading fails silently in testcases
    Validate that error conditions are caught correctly
    """
    def setUp(self):
        """
        redirect stderr for the next few tests...
        """
        sys.stderr = StringIO()

    def tearDown(self):
        sys.stderr = sys.__stderr__

    def test_unknown_format(self):
        """
        Loading data of an unknown format should fail
        """
        management.call_command(
            'loaddata',
            'bad_fixture1.unkn',
            verbosity=0,
            commit=False
            )
        self.assertEqual(
            sys.stderr.getvalue(),
            "Problem installing fixture 'bad_fixture1': unkn is not a known serialization format.\n"
            )

    def test_invalid_data(self):
        """
        Loading a fixture file with invalid data using explicit filename
        """
        management.call_command(
            'loaddata',
            'bad_fixture2.xml',
            verbosity=0,
            commit=False
            )
        self.assertEqual(
            sys.stderr.getvalue(),
            "No fixture data found for 'bad_fixture2'. (File format may be invalid.)\n"
            )

    def test_invalid_data_no_ext(self):
        """
        Loading a fixture file with invalid data without file extension
        """
        management.call_command(
            'loaddata',
            'bad_fixture2',
            verbosity=0,
            commit=False
            )
        self.assertEqual(
            sys.stderr.getvalue(),
            "No fixture data found for 'bad_fixture2'. (File format may be invalid.)\n"
            )

    def test_empty(self):
        """
        Loading a fixture file with no data returns an error
        """
        management.call_command(
            'loaddata',
            'empty',
            verbosity=0,
            commit=False
            )
        self.assertEqual(
            sys.stderr.getvalue(),
            "No fixture data found for 'empty'. (File format may be invalid.)\n"
            )

    def test_abort_loaddata_on_error(self):
        """
        If any of the fixtures contain an error, loading is aborted
        """
        management.call_command(
            'loaddata',
            'empty',
            verbosity=0,
            commit=False
            )
        self.assertEqual(
            sys.stderr.getvalue(),
            "No fixture data found for 'empty'. (File format may be invalid.)\n"
            )

    def test_error_message(self):
        """
        (Regression for #9011 - error message is correct)
        """
        management.call_command(
            'loaddata',
            'bad_fixture2',
            'animal',
            verbosity=0,
            commit=False
            )
        self.assertEqual(
            sys.stderr.getvalue(),
            "No fixture data found for 'bad_fixture2'. (File format may be invalid.)\n"
            )
