import collections
import platform
import unittest
import re
import json

from wikitextprocessor import Wtp, Page, NodeKind, WikiNode
# from wikitextparser import remove_markup, WikiText, parse
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

def parse_template(node: WikiNode, parts: list):
    try:
        t_name = node.args[0][0]
        args = node.args[1:]
        if t_name.startswith('Quote box'):
            pass
        #     quote = ""
        #     for a in node.args[1:]:
        #         if a[0].startswith('quote'):
        #             quote = a[0].split('=')[-1].strip()
        #     if len(quote) > 0:
        #         cleaned_text = re.sub(r'<ref.*$', '', quote)
        #         parts.append(f"<blockquote><p>{cleaned_text}</p></blockquote>")
        elif t_name in ['quote', 'cquote']:
            quote = args[0][0]
            cleaned_text = re.sub(r'<ref.*$', '', quote)
            parts.append(f"<blockquote><p>{cleaned_text}</p></blockquote>")
        elif t_name in ['bd']:
            if len(args) >= 2:
                parts.append(f"{args[0][0]}-{args[1][0]}")
            else:
                pass
        elif t_name.startswith('lang-'): # lang-en, lang-grc
            parts.append(f"{args[-1][0]}")
        elif t_name in ["lang"]:
            parts.append(f"{args[-1][0]}")
        elif t_name in ["le"]:
            if len(args) == 2:
                parts.append(f"{args[0][0]}({args[1][0]})")
            elif len(args) == 1:
                parts.append(f"{args[0][0]}")
            else:
                pass 
        elif t_name.startswith("link-"):
            if len(args) == 2:
                arg1 = args[0][0]
                arg2 = args[1][0]
                if arg1 != arg2: 
                    parts.append(f"{arg1}({arg2})")
                else:
                    parts.append(f"{arg1}")
        elif t_name.startswith('Cite '): # 'Cite book', 'Cite journal'
            content = None
            for x in args:
                if x[0].startswith('title'):
                    content = x[0].split('=')[-1].strip()
                    break
            if content:
                parts.append(content)
                       
        elif len(node.args) == 1:  # {{人文学科}}
            pass
        elif len(node.args) == 2:
            pass
    except Exception as e:
        print(f"{node} error: {e}")
    
    
    
    
def to_markdwon_html(node: WikiNode, node_handler_fn=None):
    """Converts a parse tree (or subtree) back to Markdown.
    If ``node_handler_fn`` is supplied, it will be called for each WikiNode
    being rendered, and if it returns non-None, the returned value will be
    rendered instead of the node.  The returned value may be a list, tuple,
    string, or a WikiNode.  ``node_handler_fn`` will be called for any
    WikiNodes in the returned value."""
    assert node_handler_fn is None or callable(node_handler_fn)

    def recurse(node):
        if isinstance(node, str):
            if "些作者會特別選擇一些文學技巧來讓讀者有意外的感受" in node:
                pass
            
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
            
            if t in ['延伸阅读']:
                pass
            
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
            # parts.append(node.args)
            # prev_list = False
            if node.args != ';':
                parts.append("<li>")
            else:
                pass
            for x in node.children:
                # if prev_list:
                #     parts.append(node.args + ":")
                parts.append(recurse(x))
                # prev_list = isinstance(x, WikiNode) and x.kind == NodeKind.LIST
            
            if node.args != ',':
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
            t_name = node.args[0][0]
            if t_name.startswith('File:') or t_name.startswith('Category'): # <LINK(['File:Gyzis 006 (Ηistoria).jpeg'], ['thumb'], ['Historia － 历史的化身', <HTML(br){} >, <LINK(['尼古拉斯·吉热斯']){} >, '（1892）']){} >
                pass
            else:
                parts.append(f'<a href="">{node.args[-1][0]}</a>') # <LINK(['日历日期'], ['日期']){} >
                parts.append(recurse(node.children))
        elif kind == NodeKind.TEMPLATE:
            global template_dict
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
            parts.append("{{" + recurse(node.args[0]) + ":")
            parts.append("|".join(map(recurse, node.args[1:])))
            parts.append("}}")
        elif kind == NodeKind.URL:
            pass # parts.append("[")
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

    return recurse(node)
 

def clean_text(text):
    text = re.sub(r'(<br>){2,}', '<br>', text)
    text = re.sub(r'</h[2-6]><br>', lambda m: m.group(0)[:-4], text)
    return text

def truncate_artitle(text):
    return text
    
def page_handler(page: Page) -> None:
    if page.model != "wikitext" or page.title.startswith("Template:") or page.redirect_to is not None or not isinstance(page.body, str):
           return None, None
    
    
    body = page.body
    
    # remove table
    body = re.sub(r':\{\|.*?\|\}', '', body, flags=re.DOTALL)
    
    
    root = ctx.parse(body, pre_expand=False)

    # html_text = ctx.node_to_html(root)
    
    text_md = to_markdwon_html(root)
    
    text = clean_text(text_md)
    text = truncate_artitle(text)
    
    # print(parsed)
    title = page.title
    
    return title, text
    

if __name__ == "__main__": 
    # path = "/lp/data/tmp/xiju.xml"
    # path = "/lp/code/wikitextprocessor/tests/test-pages-articles.xml"
    # path = "/lp/data/zhwiki/simple.xml"
    path = "/lp/data/zhwiki/zhwiki-20230601-pages-articles-multistream.xml"
    print("Parsing test data")

    ctx = Wtp(db_path="/lp/data/db/db.test", num_threads=20)
    
    
    template_dict = {}
    ret = ctx.process(
        path, page_handler, {0}
    )


    # ret = ctx.process(path, page_handler)
    
    of = open('/lp/data/zhwiki/zhwiki_html.jsonl', 'w')

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
    
# template_list = [(k[0], k[1], v) for k, v in template_dict.items()]
# sorted(template_list, key=lambda x: (x[0], x[1]))
# with open('/lp/data/zhwiki/template.txt', 'w') as of:
#     for k1, k2,  v in template_list:
#         of.write(f"{k1}\t{k2}\t{v}\n")