from django.db import models, DEFAULT_DB_ALIAS
from django.contrib.auth.models import User
from django.conf import settings


class Animal(models.Model):
    name = models.CharField(max_length=150)
    latin_name = models.CharField(max_length=150)
    count = models.IntegerField()
    weight = models.FloatField()

    # use a non-default name for the default manager
    specimens = models.Manager()

    def __unicode__(self):
        return self.name


def animal_pre_save_check(signal, sender, instance, **kwargs):
    "A signal that is used to check the type of data loaded from fixtures"
    print 'Count = %s (%s)' % (instance.count, type(instance.count))
    print 'Weight = %s (%s)' % (instance.weight, type(instance.weight))


class Plant(models.Model):
    name = models.CharField(max_length=150)

    class Meta:
        # For testing when upper case letter in app name; regression for #4057
        db_table = "Fixtures_regress_plant"


class Stuff(models.Model):
    name = models.CharField(max_length=20, null=True)
    owner = models.ForeignKey(User, null=True)

    def __unicode__(self):
        # Oracle doesn't distinguish between None and the empty string.
        # This hack makes the test case pass using Oracle.
        name = self.name
        if (settings.DATABASES[DEFAULT_DB_ALIAS]['ENGINE'] == 'django.db.backends.oracle'
            and name == u''):
            name = None
        return unicode(name) + u' is owned by ' + unicode(self.owner)


class Absolute(models.Model):
    name = models.CharField(max_length=40)

    load_count = 0

    def __init__(self, *args, **kwargs):
        super(Absolute, self).__init__(*args, **kwargs)
        Absolute.load_count += 1


class Parent(models.Model):
    name = models.CharField(max_length=10)

    class Meta:
        ordering = ('id',)


class Child(Parent):
    data = models.CharField(max_length=10)


# Models to regression test #7572
class Channel(models.Model):
    name = models.CharField(max_length=255)


class Article(models.Model):
    title = models.CharField(max_length=255)
    channels = models.ManyToManyField(Channel)

    class Meta:
        ordering = ('id',)


# Models to regression test #11428
class Widget(models.Model):
    name = models.CharField(max_length=255)

    class Meta:
        ordering = ('name',)

    def __unicode__(self):
        return self.name


class WidgetProxy(Widget):
    class Meta:
        proxy = True


# Check for forward references in FKs and M2Ms with natural keys
class TestManager(models.Manager):
    def get_by_natural_key(self, key):
        return self.get(name=key)


class Store(models.Model):
    objects = TestManager()
    name = models.CharField(max_length=255)

    class Meta:
        ordering = ('name',)

    def __unicode__(self):
        return self.name

    def natural_key(self):
        return (self.name,)


class Person(models.Model):
    objects = TestManager()
    name = models.CharField(max_length=255)

    class Meta:
        ordering = ('name',)

    def __unicode__(self):
        return self.name

    # Person doesn't actually have a dependency on store, but we need to define
    # one to test the behaviour of the dependency resolution algorithm.
    def natural_key(self):
        return (self.name,)
    natural_key.dependencies = ['fixtures_regress.store']


class Book(models.Model):
    name = models.CharField(max_length=255)
    author = models.ForeignKey(Person)
    stores = models.ManyToManyField(Store)

    class Meta:
        ordering = ('name',)

    def __unicode__(self):
        return u'%s by %s (available at %s)' % (
            self.name,
            self.author.name,
            ', '.join(s.name for s in self.stores.all())
        )


class NKManager(models.Manager):
    def get_by_natural_key(self, data):
        return self.get(data=data)


class NKChild(Parent):
    data = models.CharField(max_length=10, unique=True)
    objects = NKManager()

    def natural_key(self):
        return self.data

    def __unicode__(self):
        return u'NKChild %s:%s' % (self.name, self.data)


class RefToNKChild(models.Model):
    text = models.CharField(max_length=10)
    nk_fk = models.ForeignKey(NKChild, related_name='ref_fks')
    nk_m2m = models.ManyToManyField(NKChild, related_name='ref_m2ms')

    def __unicode__(self):
        return u'%s: Reference to %s [%s]' % (
            self.text,
            self.nk_fk,
            ', '.join(str(o) for o in self.nk_m2m.all())
        )


# ome models with pathological circular dependencies
class Circle1(models.Model):
    name = models.CharField(max_length=255)

    def natural_key(self):
        return self.name
    natural_key.dependencies = ['fixtures_regress.circle2']


class Circle2(models.Model):
    name = models.CharField(max_length=255)

    def natural_key(self):
        return self.name
    natural_key.dependencies = ['fixtures_regress.circle1']


class Circle3(models.Model):
    name = models.CharField(max_length=255)

    def natural_key(self):
        return self.name
    natural_key.dependencies = ['fixtures_regress.circle3']


class Circle4(models.Model):
    name = models.CharField(max_length=255)

    def natural_key(self):
        return self.name
    natural_key.dependencies = ['fixtures_regress.circle5']


class Circle5(models.Model):
    name = models.CharField(max_length=255)

    def natural_key(self):
        return self.name
    natural_key.dependencies = ['fixtures_regress.circle6']


class Circle6(models.Model):
    name = models.CharField(max_length=255)

    def natural_key(self):
        return self.name
    natural_key.dependencies = ['fixtures_regress.circle4']


class ExternalDependency(models.Model):
    name = models.CharField(max_length=255)

    def natural_key(self):
        return self.name
    natural_key.dependencies = ['fixtures_regress.book']


class Tagger(models.Model):
    name = models.CharField(max_length=20)
    topics = models.ManyToManyField("Tag", through="TaggerTag")

    def natural_key(self):
        return self.name


class Posting(models.Model):
    tagger = models.ForeignKey(Tagger)
    text = models.TextField()
    time = models.DateTimeField()

    def natural_key(self):
        return (self.tagger.name, self.time)
    natural_key.dependencies = ['fixtures_regress.tagger']


class Tag(models.Model):
    name = models.CharField(max_length=20)
    postings = models.ManyToManyField(Posting, through="PostingTag")

    def natural_key(self):
        return self.name


class PostingTag(models.Model):
    tag = models.ForeignKey(Tag)
    posting = models.ForeignKey(Posting)

    def natural_key(self):
        return (self.tag.natural_key(), self.posting.natural_key())


class TaggerTag(models.Model):
    tagger = models.ForeignKey(Tagger)
    tag = models.ForeignKey(Tag)

    def natural_key(self):
        return (self.tag.natural_key(), self.tagger.natural_key())
