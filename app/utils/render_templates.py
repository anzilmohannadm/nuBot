import traceback
from string import Template


def user_mention(str_editor,str_page_title,str_url, str_space_name, str_date):
    try:
        with open("app/templates/user-mention.html", "r") as ins_file:
            str_html_template = Template(ins_file.read())
        str_html = str_html_template.substitute(str_editor = str_editor,str_page_title = str_page_title,str_url = str_url, str_space_name = str_space_name, str_date = str_date)
        return str_html
    except Exception:
        traceback.print_exc()

