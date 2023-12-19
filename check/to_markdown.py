import re
from markdownify import markdownify
import json


def to_markdown(html_content):
    if not html_content or len(html_content) == 0:
        return ""
    markdown_str = markdownify(html_content, heading_style="ATX")
    return markdown_str


def clean_markdown(markdown_str):
    if not markdown_str or len(markdown_str) == 0:
        return ""

    # 使用正则表达式匹配图片, 包含换行
    image_pattern = r'!\[(.*?)\]\((.*?)\)\n*'
    markdown_str = re.sub(image_pattern, "", markdown_str)

    # 使用正则表达式匹配链接,替换为文本
    def replace_link(match):
        return match.group(1)

    link_pattern = r'\[(.*?)\]\((.*?)\)\n*'
    markdown_str = re.sub(link_pattern, replace_link, markdown_str)

    markdown_str = markdown_str.replace('\xa0', ' ')
    return markdown_str



def read_json_in(in_file: str):
    j_list = []
    for line in open(in_file):
        j_list.append(json.loads(line))
    return j_list


def write_out(d, out_file):
    with open(out_file, 'w') as of:
        for x in d:
            j = json.dumps(x, ensure_ascii=False)
            of.write(f"{j}\n")


def clear_makrdown(markdown_str):
    markdown_str = re.sub(r'\n[ \u3000]+\n', '\n\n', markdown_str)  # 空格 和全角空格
    markdown_str = re.sub(r"\n{3,}", "\n\n", markdown_str)

    markdown_str = markdown_str.strip()

    # remove * / space
    while markdown_str[-1] in ['*', " ", "\n"]:
        markdown_str = markdown_str[:-1]

    return markdown_str



if __name__ == "__main__": 
    # logging.basicConfig(level=logging.INFO)  # 设置日志级别为 INFO
    import argparse

    parser = argparse.ArgumentParser(description="to_markdown")
    parser.add_argument("--input", type=str, required=True, help="in xml file")
    parser.add_argument("--output", type=str, required=True, default="wiki.jsonl", help="output file")
    args = parser.parse_args()
    
    # in_file = 'zhwiki_html.jsonl'
    in_file = args.input
    out_file = args.output
    

    j_list = read_json_in(in_file)

    error_count = 0
    for j in j_list:
        html_text = j['text']
        if len(html_text) == 0:
            continue

        try:
            md = to_markdown(html_text)
        except Exception as e:
            print(f"{e} : {html_text}")
            error_count += 1
            md = "-1"

        clean_md = clean_markdown(md)
        j['md'] = clean_md
    
    
    valid_j_list = list(filter(lambda x: 'md' in x and len(x['md']) > 50, j_list)) # 91.7%

    out_j_list = []
    for j in valid_j_list:
        item_dict = {"title": j["title"], "content": j["md"]}
        out_j_list.append(item_dict)


    # 简体
    from opencc import OpenCC
    cc = OpenCC('t2s')
    for j in out_j_list:
        j['content'] = cc.convert(['content'])
    
   
    write_out(out_j_list, out_file)