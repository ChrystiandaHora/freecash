from django.test import TestCase
from core.templatetags.core_tags import add_class, replace, month_name, split
from django import forms

class CoreTemplateTagsTestCase(TestCase):
    def test_add_class_filter(self):
        class TestForm(forms.Form):
            name = forms.CharField()
        
        form = TestForm()
        field = form["name"]
        # When passed a form field, it should return widget HTML with the class
        result = add_class(field, "my-custom-class")
        self.assertIn('class="my-custom-class"', result)

    def test_replace_filter(self):
        # Specific case: replace:"_ ," should replace _ with space
        self.assertEqual(replace("Hello_World", "_ ,"), "Hello World")
        # Generic case: split by comma
        self.assertEqual(replace("a-b-c", "-,*"), "a*b*c")

    def test_month_name_filter(self):
        self.assertEqual(month_name(1), "Janeiro")
        self.assertEqual(month_name(12), "Dezembro")
        self.assertEqual(month_name(99), 99) # Fallback

    def test_split_filter(self):
        self.assertEqual(split("a,b,c", ","), ["a", "b", "c"])
        self.assertEqual(split("a-b", "-"), ["a", "b"])
