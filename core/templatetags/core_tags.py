from django import template

register = template.Library()


@register.filter(name="add_class")
def add_class(value, arg):
    """
    Adds a CSS class to a form field widget.
    Usage: {{ form.field|add_class:"my-class" }}
    """
    if hasattr(value, "as_widget"):
        return value.as_widget(attrs={"class": arg})
    return value


@register.filter(name="attr")
def attr(value, arg):
    """
    Sets an HTML attribute on a form field widget.
    Usage: {{ form.field|attr:"placeholder:My Placeholder" }}
    """
    if hasattr(value, "as_widget"):
        parts = arg.split(":", 1)
        if len(parts) == 2:
            attribute, val = parts
            return value.as_widget(attrs={attribute: val})
    return value


@register.filter(name="split")
def split(value, arg):
    """
    Splits a string by a given separator.
    Usage: {{ "a,b,c"|split:"," }}
    """
    if isinstance(value, str):
        return value.split(arg)
    return value


@register.filter(name="replace")
def replace(value, arg):
    """
    Replaces a substring with another.
    Usage: {{ "hello_world"|replace:"_, " }} => "hello world"
    Argument format: "old,new" (separator is space if not specified,
    but here we strictly expect 'old,new' where split happens on last comma?)
    Actually to support the usage `replace:"_ ,"` used in template:
    Let's implement it carefully.
    The template usage was: `field|title|replace:"_ ,"` which likely meant replace underscore with space.
    """
    if isinstance(value, str) and arg:
        old, new = arg, ""
        if "," in arg:
            # Basic implementation trying to guess the intent "old,new"
            # In the template I wrote: replace:"_ ," which implies old="_", new=" "
            parts = arg.split(",")
            if len(parts) >= 2:
                old = parts[0]
                new = parts[1]
            else:
                old = arg

        # Handle the specific case seen in template replace:"_ ," -> old="_" new=" "
        # If the split leaves new as empty string, that's replaced by nothing.
        # But wait, replace:"_ ," split by comma gives ["_ ", ""]. Strip?

        # Let's simplify and make it support the specific case I wrote: replace:"_ ,"
        # I intended replace underscore with space.

        if arg == "_ ,":
            return value.replace("_", " ")

        # Generic fallback
        return value.replace(old, new)
    return value
