from django.template import Context, Template


def render_message(template_str: str, context: dict) -> str:
    """
    Renderiza um template de texto com placeholders no formato {{ var }}
    substituindo-os pelos valores do dicionário context.

    Exemplo:
        template = "Olá {{ nome }}, seu valor é {{ valor }}"
        ctx = {"nome": "Maria", "valor": "R$ 100,00"}
        output = render_message(template, ctx)
    """
    # Criamos o objeto Template do Django e renderizamos com o Context fornecido
    tpl = Template(template_str)
    ctx = Context(context)
    return tpl.render(ctx)
