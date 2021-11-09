import csv
import logging
import os
from subprocess import Popen, DEVNULL
import jinja2
from jinja2.environment import Template
import tempfile
import shutil
import argparse

#
# USAGE:
# 0) Create single-file TEX files to be generated in src/
# 1) Download team data in "Tab-separated value (.tsv, current sheet)" format e.g. (local.tsv)
# 2) In the TEX file provide \VAR{csapatnev} where the team name is to be written
# 3) In the head of do.py, fill out possible_categories; here point to the TEX files created (without src/)
# 4) Fix header names from CSV if it changed
# 5) Run `python do.py local.tsv`
#

possible_categories = {'C kategória': 'HUN/15HC.tex', 'D kategória': 'HUN/15HD.tex', 'E kategória': 'HUN/15HE.tex', 'E+ kategória': 'HUN/15HEp.tex'} #, 'F kategória': 'C.tex', 'F+ kategória': 'C.tex', 'K kategória': 'C.tex', 'K+ kategória': 'C.tex', }
templated_files = ['magic/feladat.tex.j2']
category_header = 'Kategória'
teamname_header = 'Csapatnév'
place_header = 'Helyszín'



# I/O
def get_place_directory(place):
    return os.path.join('target', place)

def ensure_dir(path):
    if not os.path.isdir(path):
        os.mkdir(path)
def initialize_output_directories():
    ensure_dir('target')

def load_templates():
    # JINJA2 latex templating https://www.miller-blog.com/latex-with-jinja2/
    latex_jinja_env = jinja2.Environment(
        block_start_string='\BLOCK{',
        block_end_string='}',
        variable_start_string='\VAR{',
        variable_end_string='}',
        comment_start_string='\#{',
        comment_end_string='}',
        line_statement_prefix='%%%%%%%%%%%%%%', # TODO hack, find out what this really do
        line_comment_prefix='%#',
        trim_blocks=True,
        autoescape=False,
        loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), 'src'))
    )
    templates = {}

    for templated_fn in templated_files:
        assert templated_fn.endswith('.j2') # for JinJa template
        output_fn = templated_fn[:-3]
        templates[output_fn] = latex_jinja_env.get_template(templated_fn)
    return templates

class LatexCompileError(Exception):
    def __init__(self, *args):
        super().__init__(*args)

def sanitize_teamname(s):
    return s.replace("_", "\\_")

def compile_tex(input_fn, output_name, output_dir):
    '''
    Parameters:
    input_fn: filename relative to src/
    output_name: The PDF-s name, without .pdf (must be unique in the same place)
    output_dir: The PDF's output directory. Probably something like ../target/Budapest
    '''

    cmds = ['pdflatex', '-halt-on-error', f'-jobname={output_name}', f'-output-directory={output_dir}', input_fn]
    # not used for real command
    cmd_sanitized_for_logging = ' '.join([arg.replace(' ', '\\ ') for arg in cmds])
    logging.debug(f"Running command {cmds}")
    logging.debug(f"   $ {cmd_sanitized_for_logging}")
    p = Popen(cmds, stdin=None, stdout=DEVNULL, stderr=DEVNULL, cwd=os.path.abspath('src'))
    p.communicate()
    if p.returncode != 0:
        raise LatexCompileError(f"Failed to compile from {input_fn}. The file is still available for debugging")

templates = load_templates()

def instantiate_template(template, output_fn, **kwargs):
    with open(output_fn, 'w') as f:
        f.write(template.render(**kwargs))

def lpad(s, n):
    s = str(s)
    l = len(s)
    if l < n:
        return (n-l)*"0"+s
    return s

def handle_team(id, row):
    logging.debug('Adding new team')
    category = row[category_header]
    teamname = row[teamname_header]
    place = row[place_header]
    good = True # write all warnings
    logging.info(f'Adding team {teamname}')
    ensure_dir(get_place_directory(place))

    if category not in possible_categories:
        logging.error(f"Error: {category} not in {[*possible_categories.keys()]}. Skipping.")
        good = False
    if not good:
        return

    ids = lpad(id,3)
    # Instantiate templates
    for template_id in templates:
        output_tex = os.path.join("src", template_id)
        logging.debug(f"{teamname}; {place}; {category} -> {output_tex}")
        instantiate_template(templates[template_id], output_tex, csapatnev=sanitize_teamname(teamname))
    # compile TEX file into PDF
    main_tex = possible_categories[category]
    output_pdf = f"{ids}"
    output_dir = os.path.join("..", "target", place)
    try:
        compile_tex(main_tex, output_pdf, output_dir)
    except Exception:
        logging.error(f"Error happened while compiling {output_tex}")
        #raise


def main():
    parser = argparse.ArgumentParser(usage="""
USAGE:
1) Create single-file TEX files to be generated in src/
2) Download team data in "Tab-separated value (.tsv, current sheet)" format e.g. (local.tsv)
3) In the TEX file provide \VAR{csapatnev} where the team name is to be written
4) In the head of do.py, fill out possible_categories; here point to the TEX files created (without src/)
5) Fix header names from CSV if it changed
6) Run `python do.py local.tsv`

""")
    parser.add_argument("--loglevel", choices=["DEBUG", "INFO", "WARNING", "ERROR"], nargs='?', default="INFO")
    parser.add_argument("tsvfile")
    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel)

    initialize_output_directories()

    try:
        with open(args.tsvfile, 'r', newline='') as f:
            reader = csv.DictReader(f, delimiter='\t', quotechar='"')
            id=0
            if len(set(reader.fieldnames)) != len(reader.fieldnames):
                pass#raise ValueError("Duplicate fieldname! Not going to proceed! Fix team table")
            for row in reader:
                handle_team(id, row)
                id += 1
    except Exception:
        print("Some error happened. If it was parsing, try")
        print("  - Running in debug level: python do.py --loglevel=DEBUG")
        print("  - Checking the output file at target/location/n.tex. Which file failed should be easy to determine.")
        raise

main()
