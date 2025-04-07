"""
This file parses the documents into text, handling different file types, before chunking the documents.
"""

import os
import docx
import mistletoe
from bs4 import BeautifulSoup
import re
from docx import Document
from constants import *

"""
Extract text from a TXT file.
Parameters: txt_path: the filepath of the TXT file
Returns: the text in the file
"""
def extract_text_from_txt(txt_path: str) -> str:
    with open(txt_path, 'r', encoding='utf-8') as file:
        return file.read()

"""
Extract text from a DOCX file.
Parameters: docx_path: the filepath of the DOCX file
Returns: the text in the file
"""
def extract_text_from_docx(docx_path: str) -> str:
    text = ""
    doc = Document(docx_path)

    for paragraph_or_table in doc.iter_inner_content():        
        # If this element is a paragraph, add the paragraph's text to all the text
        if isinstance(paragraph_or_table, docx.text.paragraph.Paragraph):
            text += (paragraph_or_table.text + "\n\n")
        else: # It's a table
            text += (parse_docx_table(paragraph_or_table) + "\n\n")

    return text


"""
Parse a Markdown file to text.
Parameters:
    - file_path: the path of the Markdown file
    - indicate_tables: whether to indicate tables in the parsed text file. 
                            If true, every table will have the text "Table:" above it. If false, it will not.
    - table_separator: the separator for items in a table row

Returns: The parsed text 
"""
def extract_text_from_markdown(file_path: str, indicate_tables: bool = True, table_separator: str = ",") -> str:

    # First parse the Markdown to HTML
    with open(file_path, "r") as file:
        html_text = mistletoe.markdown(file) # the Markdown text parsed to HTML

    soup = BeautifulSoup(html_text, "html.parser") 

    # Now, for each HTML table in the HTML text, convert that table to an HTML paragraph, then replace the table with that paragraph.
    # (This is because BeautifulSoup doesn't parse tables correctly)
    new_html_text = html_text # the HTML text with tables converted to paragraphs
    tables = soup.find_all(name="table") # Get all the tables by getting the text with the "<table>" HTML tag

    for table_tag in tables:
        table_as_paragraph = parse_html_table_to_paragraph(str(table_tag), indicate_table=indicate_tables, separator=table_separator)
        new_html_text = new_html_text.replace(str(table_tag), table_as_paragraph)

    soup2 = BeautifulSoup(new_html_text, "html.parser")

    return soup2.get_text()

"""
Parse a table in a DOCX file to text
Parameters: table: the DOCX table to parse
Returns: the table parsed to text
"""
def parse_docx_table(table: docx.table.Table) -> str:
    table_as_string = "Table:\n"
    num_cols = len(table.columns)

    # nested list of all the table cells. Each inner list is the cells in each row. 
    # Also, if the table has more than 1 column, remove newline characters from within table cells
    cell_list = [[cell.text.replace("\n", " ") if num_cols > 1 else cell.text for cell in row.cells] 
                 for row in table.rows] 

    # Add each table row to the string, separated by a comma
    for row in cell_list:
        table_as_string += (",".join(row) + "\n")
    
    return table_as_string

"""
Converts an HTML table to an HTML paragraph containing the text in the table. 
(This way, the HTML parser can parse the table as a paragraph).

Precondition: The HTML text must contain a single HTML table and nothing else.

Parameters:
    - html_table_text: the HTML markup containing the table
    - separator: the separator for table items
    - indicate_tables: whether to indicate tables in the paragraph. 
                            If true, the table will have the text "Table:" above it in the paragraph. If false, it will not.
Returns: the HTML paragraph with the table's text
"""
def parse_html_table_to_paragraph(html_table_text: str, indicate_table: bool = True, separator: str = ",") -> str:
    soup = BeautifulSoup(html_table_text, "html.parser")
    table_as_string = "Table:\n" if indicate_table else ""
    table_tags = soup.find_all("table") # find all <table> tags

    for table_tag in table_tags:
        tr_tags = table_tag.find_all("tr") # find <tr> (table row) tags

        # If there are table rows, find all the table data in the rows (the <td> tags)
        if len(tr_tags) > 0:
            for row in tr_tags:
                td_or_th_tags = row.find_all(['th', 'td']) # Find all the <th> (table header) and <td> (table data) tags. 

                # If there is table data or a table header, add it to the string and separate the data with the separator
                if len(td_or_th_tags) > 0:
                    for i in range(len(td_or_th_tags)):

                        # Get the contents of the tag and concatenate them into a string
                        tag_contents = td_or_th_tags[i].contents
                        for j in range(len(tag_contents)):
                            tag_contents[j] = str(tag_contents[j]) 
                            
                        table_as_string += "".join(tag_contents) 
                        
                        if i < len(td_or_th_tags) - 1:
                            table_as_string += separator

                table_as_string += "\n" # Add a newline after each row

    return "<p>" + table_as_string + "</p>" # Put the string in an HTML paragraph element, to parse it as a paragraph instead of a table

