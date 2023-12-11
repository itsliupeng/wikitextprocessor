import collections
import platform
import unittest
import re
import json
import logging

from wikitextprocessor import Wtp, Page, NodeKind, WikiNode
from wikitextprocessor import parser
from wikitextprocessor.node_expand import to_attrs, ALLOWED_HTML_TAGS

kind_to_level = {
    NodeKind.LEVEL2: "h2",
    NodeKind.LEVEL3: "h3",
    NodeKind.LEVEL4: "h4",
    NodeKind.LEVEL5: "h5",
    NodeKind.LEVEL6: "h6",
}

def is_chinese(text):
    pattern = re.compile(r'^[\u4e00-\u9fff]+$')
    return bool(pattern.match(text))

def page_cb(page):
    # Note: this may be called in a separate thread and thus cannot
    # update external variables
    return page.title, page.redirect_to


def get_content_arg(args):
    content_args = None
    for i in range(1, len(args)+1):
        if len(args[-i]) > 0:
            content_args = args[-i]
    return content_args
  
def remove_empty_arg(args):
    return list(filter(lambda x: len(x) > 0, args))      
    
def parse_template(node: WikiNode, parts: list):
    try:
        t_name = node.args[0][0]
        args = node.args[1:]
        if t_name.startswith('Quote box'):
            pass
        elif t_name in ['quote', 'cquote']:
            quote = recurse(node.args)
            cleaned_text = re.sub(r'<ref.*$', '', quote)
            parts.append(f"<blockquote><p>{cleaned_text}</p></blockquote>")
        elif t_name in ['bd']:
            args = remove_empty_arg(args)
            if len(args) >= 2:
                parts.append(f"{args[0][0]}-{args[1][0]}")
            elif len(args) == 1:
                parts.append(f"{args[0][0]}-")
            else:
                pass
        elif t_name.startswith('lang-'): # lang-en, lang-grc
            content_arg = get_content_arg(args)
            if content_arg:
                parts.append(f"{content_arg[0]}")
        elif t_name in ["lang"]:
            content_arg = get_content_arg(args)
            if content_arg:
                parts.append(f"{content_arg[0]}")
        elif t_name in ["le"]:
            if len(args) == 2:
                arg1 = args[0]
                arg2 = args[1]
                if  len(arg1) > 0 and len(arg2) > 0 and  arg1[0] != arg2[0]: 
                    parts.append(f"{arg1[0]}({arg2[0]})")
                else:
                    content_arg = get_content_arg(args)
                    if content_arg:
                        parts.append(f"{content_arg[0]}")
            elif len(args) == 1:
                parts.append(f"{args[0][0]}")
            else:
                pass 
        elif t_name.startswith("link-"):
            if len(args) == 2:
                arg1 = args[0]
                arg2 = args[1]
                if  len(arg1) > 0 and len(arg2) > 0 and  arg1[0] != arg2[0]: 
                    parts.append(f"{arg1[0]}({arg2[0]})")
                else:
                    content_arg = get_content_arg(args)
                    if content_arg:
                        parts.append(f"{content_arg[0]}")
        elif t_name.startswith('Cite '): # 'Cite book', 'Cite journal'
            content = None
            for x in args:
                if len(x) > 0 and x[0].strip().startswith('title'):
                    content = x[0].split('=')[-1].strip()
                    break
            if content:
                parts.append(content)
                       
        elif len(node.args) == 1:  # {{人文学科}}
            pass
        elif len(node.args) == 2:
            pass
    except Exception as e:
        print(f"error in {node} : {e}")
    

def recurse(node, node_handler_fn=None):
    if isinstance(node, str):
        # Certain constructs needs to be protected so that they don't get
        # parsed when we convert back and forth between wikitext and parsed
        # representations.
        node = re.sub(r"(?si)\[\[", "[<noinclude/>[", node)
        node = re.sub(r"(?si)\]\]", "]<noinclude/>]", node)
        node = re.sub(r"<ref.*?</ref>", "", node)
        return node
    if isinstance(node, (list, tuple)):
        return "".join(map(recurse, node))
    if not isinstance(node, WikiNode):
        raise RuntimeError("invalid WikiNode: {}".format(node))

    if node_handler_fn is not None:
        ret = node_handler_fn(node)
        if ret is not None and ret is not node:
            if isinstance(ret, (list, tuple)):
                return "".join(recurse(x) for x in ret)
            return recurse(ret)

    kind = node.kind
    parts = []
    if kind in kind_to_level:
        tag = kind_to_level[kind]
        t = recurse(node.args)

        if t in ['脚注', '腳註', '参考文献', '參考文獻', '外部链接', '外部連結', '参考', '參考', '注释', '註釋']:
            pass
        else:
            parts.append(f"<{tag}>{t}</{tag}>")
            parts.append(recurse(node.children))
    elif kind == NodeKind.HLINE:
        parts.append("<br>")
    elif kind == NodeKind.LIST:
        if node.children[0].args == "*":
            tag = "ul"
        elif node.children[0].args == "**":
            tag = "ol"
        else:
            tag = "ul"
        parts.append(f"<{tag}>{recurse(node.children)}</{tag}>")
    elif kind == NodeKind.LIST_ITEM:
        assert isinstance(node.args, str)
        if node.args != ';':
            parts.append("<li>")
        else:
            pass
        for x in node.children:
            parts.append(recurse(x))

        if node.args != ';':
            parts.append("</li>")
        # filter \n
        parts = [x for x in parts if x != "\n"]
    elif kind == NodeKind.PRE:
        parts.append("<pre>")
        parts.append(recurse(node.children))
        parts.append("</pre>")
    elif kind == NodeKind.PREFORMATTED:
        parts.append(recurse(node.children))
    elif kind == NodeKind.LINK:
        if len(node.args[0]) == 0:
            pass
        else:
            t_name = node.args[0][0]
            if not isinstance(t_name, str):
                print(f"check: LINK not string {t_name}")
                pass
            else:
                if t_name.startswith('File:') or t_name.startswith('Category'):
                    pass
                else:
                    args = remove_empty_arg(node.args)
                    if len(args) > 0:
                        content = recurse(args[-1]) if isinstance(args[-1], WikiNode) else args[-1][0]
                        if isinstance(args[-1], WikiNode):
                            print(f"check {content}")
                        parts.append(f'<a href="">{content}</a>')  # <LINK(['日历日期'], ['日期']){} >
                        parts.append(recurse(node.children))
    elif kind == NodeKind.TEMPLATE:
        global template_dict
        if len(node.args[0]) > 0:
            t_name = node.args[0][0]
            key = (t_name, len(node.args))
            if key not in template_dict and not is_chinese(t_name):
                template_dict[key] = node

        parse_template(node, parts)

    elif kind == NodeKind.TEMPLATE_ARG:
        parts.append("{{{")
        parts.append("|".join(map(recurse, node.args)))
        parts.append("}}}")
    elif kind == NodeKind.PARSER_FN:
        pass # parts.append("{{" + recurse(node.args[0]) + ":")
        # parts.append("|".join(map(recurse, node.args[1:])))
        # parts.append("}}")
    elif kind == NodeKind.URL:
        pass  # parts.append("[")
        # if node.args:
        #     parts.append(recurse(node.args[0]))
        #     for x in node.args[1:]:
        #         parts.append(" ")
        #         parts.append(recurse(x))
        # parts.append("]")
    elif kind == NodeKind.TABLE:
        pass
        # parts.append("\n{{| {}\n".format(to_attrs(node)))
        # parts.append(recurse(node.children))
        # parts.append("\n|}\n")
    elif kind == NodeKind.TABLE_CAPTION:
        pass
        # parts.append("\n|+ {}\n".format(to_attrs(node)))
        # parts.append(recurse(node.children))
    elif kind == NodeKind.TABLE_ROW:
        pass
        # parts.append("\n|- {}\n".format(to_attrs(node)))
        # parts.append(recurse(node.children))
    elif kind == NodeKind.TABLE_HEADER_CELL:
        pass
        # if node.attrs:
        #     parts.append("\n! {} |{}\n"
        #                  .format(to_attrs(node),
        #                          recurse(node.children)))
        # else:
        #     parts.append("\n!{}\n"
        #                  .format(recurse(node.children)))
    elif kind == NodeKind.TABLE_CELL:
        pass
        # if node.attrs:
        #     parts.append("\n| {} |{}\n"
        #                  .format(to_attrs(node),
        #                          recurse(node.children)))
        # else:
        #     parts.append("\n|{}\n"
        #                  .format(recurse(node.children)))
    elif kind == NodeKind.MAGIC_WORD:
        parts.append("\n{}\n".format(node.args))
    elif kind == NodeKind.HTML:
        if node.args == 'ref':
            pass
        elif node.children:
            parts.append("<{}".format(node.args))
            if node.attrs:
                parts.append(" ")
                parts.append(to_attrs(node))
            parts.append(">")
            parts.append(recurse(node.children))
            parts.append("</{}>".format(node.args))
        else:
            parts.append("<{}".format(node.args))
            if node.attrs:
                parts.append(" ")
                parts.append(to_attrs(node))
            if ALLOWED_HTML_TAGS.get(node.args, {
                "no-end-tag": True}).get("no-end-tag"):
                parts.append(">")
            else:
                parts.append(" />")
    elif kind == NodeKind.ROOT:
        parts.append(recurse(node.children))
    elif kind == NodeKind.BOLD:
        parts.append("<b>")
        parts.append(recurse(node.children))
        parts.append("</b>")
    elif kind == NodeKind.ITALIC:
        parts.append("<i>")
        parts.append(recurse(node.children))
        parts.append("</i>")
    else:
        raise RuntimeError("unimplemented {}".format(kind))

    trans_parts = []
    for x in parts:
        if x == "\n":
            x = "<br>"
        x = re.sub("\n\n", "<br>", x)
        x = re.sub("\n", "", x)
        trans_parts.append(x)

    ret = "".join(trans_parts)
    ret = re.sub("\n\n", "<br>", ret)
    ret = re.sub(r'^(<br>)+', '', ret)

    return ret
     
  
    
def to_markdwon_html(node: WikiNode, node_handler_fn=None):
    """Converts a parse tree (or subtree) back to Markdown.
    If ``node_handler_fn`` is supplied, it will be called for each WikiNode
    being rendered, and if it returns non-None, the returned value will be
    rendered instead of the node.  The returned value may be a list, tuple,
    string, or a WikiNode.  ``node_handler_fn`` will be called for any
    WikiNodes in the returned value."""
    assert node_handler_fn is None or callable(node_handler_fn)

    try:
        ret = recurse(node)
    except Exception as e:
        pass
    return ret
 

def clean_text(text):
    text = re.sub(r'(<br>){2,}', '<br>', text)
    text = re.sub(r'</h[2-6]><br>', lambda m: m.group(0)[:-4], text)
    return text



def remove_last_heading_content(html):
    pattern = r'<h([2-6])>.*?</h\1>$'
    return re.sub(pattern, '', html)

    
def page_handler(page: Page) -> None:
    if page.model != "wikitext" or page.title.startswith("Template:") or page.redirect_to is not None or not isinstance(page.body, str):
           return None, None
    
    
    body = page.body
    
    # remove 目录
    body = re.sub(r'__TOC__', '', body, flags=re.DOTALL)
    
    # remove table
    body = re.sub(r'\{\|.*?\|\}', '', body, flags=re.DOTALL)
    # remove all html tag
    body = re.sub(r'<([^>]+)>.*?</\1>', '', body, flags=re.DOTALL)
    
    
    root = ctx.parse(body, pre_expand=False)  
      
    text_md = to_markdwon_html(root)
    
    text = clean_text(text_md)
    text = remove_last_heading_content(text)

    title = page.title
    
    return title, text
    

if __name__ == "__main__": 
    logging.basicConfig(level=logging.INFO)  # 设置日志级别为 INFO
    import argparse

    parser = argparse.ArgumentParser(description="wiki_parser")
    parser.add_argument("--input", type=str, required=True, help="in xml file")
    parser.add_argument("--output", type=str, required=True, default="wiki.jsonl", help="output file")
    parser.add_argument("--num-threads", type=int, default=1, help="num threads")
    parser.add_argument("--db-path", type=str, default="/tmp/db", help="db path")
    parser.add_argument("--template", type=str, default="template.txt", help="saved template path")

    args = parser.parse_args()
    
    
    # path = "/lp/data/tmp/xiju.xml"
    # path = "/lp/code/wikitextprocessor/tests/test-pages-articles.xml"
    # path = "/lp/data/zhwiki/simple.xml"
    # path = "/lp/data/wiki/enwiki-20230801-pages-articles.xml"
    # path = "/lp/data/zhwiki/zhwiki-20230720-pages-articles-multistream.xml"
    # print("Parsing test data")
    
    path = args.input
    output_file = args.output
    db_path =args.db_path
    num_threads = args.num_threads
    

    ctx = Wtp(db_path=db_path, num_threads=num_threads)
    template_dict = {}
    
    

    # body = """

    # """
    # ctx.title = 'test'
    # root = ctx.parse(body, pre_expand=False)

    # print('Done')

    
    
    ret = ctx.process(
        path, page_handler, {0}
    )

    of = open(output_file, 'w')

    num = 0
    for title, text in ret:
        if text is None:
            continue
        
        j = {'title': title, 'text': text}
        of.write(f"{json.dumps(j, ensure_ascii=False)}\n")    
        
        num += 1
        if num % 10000 == 0:
            print(f"processed {num} articles.")
            
    of.close() 
    
template_list = [(k[0], k[1], v) for k, v in template_dict.items()]
sorted(template_list, key=lambda x: (x[0], x[1]))
with open(args.template, 'w') as of:
    for k1, k2,  v in template_list:
        of.write(f"{k1}\t{k2}\t{v}\n")