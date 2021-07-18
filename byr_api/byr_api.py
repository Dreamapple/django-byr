

import time
import json
import logging
import requests
import collections
from pathlib import Path
from datetime import datetime, timedelta, date

from .storage import SpiderStorage, SpiderQueue

logging.basicConfig(level=logging.INFO)


def convert_str_to_datetime(s):
    if isinstance(s, datetime):
        return s
    if s == "刚刚":
        return datetime.now()
    if s.endswith("分钟前"):
        return datetime.now() - timedelta(0, int(s[:-3]) * 60)
    if s.startswith("今天"):
        s = s.replace("今天", date.today().strftime("%Y-%m-%d"))
        return datetime.strptime(s, "%Y-%m-%d %H:%M")
    if len(s) == 10:
        return datetime.strptime(s, "%Y-%m-%d")
    if len(s) == 16:
        return datetime.strptime(s, "%Y-%m-%d %H:%M")
    if len(s) == 19:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    print("call convert_str_to_datetime(%s)" % s)
    assert False


def force_decode_json(text):
    while True:
        try:
            return json.loads(text)
        except json.decoder.JSONDecodeError as e:
            if e.msg == "Invalid \\escape":
                if text[e.pos] == "\\":
                    text = text[:e.pos] + "\\\\" + text[e.pos+1:]
                    continue
            logging.exception(e)
            return {}


class BasePage:
    def __init__(self, r):
        self.response_ = r


    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.response_)
    

class TopTen(BasePage):
    def __str__(self):
        result = []
        for d in self.data_['data']:
            result.append("# " + d['title'])
            result.append("  " + d['content'])
            result.append("--" * 20)
        return '\n'.join(result)

    def v2ex_json(self):
        ret = []

        for article in self.response_.json()["data"]:
            topic_obj = {
                "category": {
                    "code": article["board_name"],
                    "name": article["board_description"],
                },
                "author": {
                    "username": article["user"]["id"],
                    "user": article["user"]["user_name"],
                    "avatar": article["user"]["face_url"]
                },
                "topic_sn": article["board_name"]+"_"+str(article["id"]),
                "click_num": 0,
                "comment_num": None,
                "last_comment_user": "",
                "last_comment_time": None,
                "title": article["title"],
                "markdown_content": article["content"],
                "add_time": datetime.fromtimestamp(article["post_time"]).isoformat(),
                "update_time": None
            }

            ret.append(topic_obj)

        return ret;

class Sections(BasePage):
    def __iter__(self):
        if not self.data_:
            return
        for b in self.data_['data']['boards']:
            yield from self.get_boards(b)

    def get_boards(self, board):
        try:
            if board.get('dir'):
                for child in board['children']:
                    yield from self.get_boards(child)
            else:
                yield board
        except:
            print("call get_boards(%s)" % board)
            raise

    @staticmethod
    def from_data(data):
        s = Sections(None)
        s.data_ = data
        return s

class Section(BasePage):
    def v2ex_node_obj(self):
        data = self.response_.json()["data"]

        node_obj = {
            "avatar": None,
            "header_color": "#001D25",
            "favorite": [0],
            "name": data["name"],
            "desc": data["description"],
            "total": int(data["pagination"]["total"])
        }
        return node_obj

    def v2ex_topic_obj(self):
        data = self.response_.json()["data"]
        ret = List()

        for post in data["posts"]:
            if post["tag"] == "top":
                continue
            topic_obj = {
                "category": {
                    "code": data["name"],
                    "name": data["name"],
                },
                "author": {
                    "username": post["poster"],
                    "user": post["poster"],
                    "avatar": "https://bbs.byr.cn/img/face_default_m.jpg"
                },
                "topic_sn": data["name"] + "_" + str(post["gid"]),
                "click_num": 0,
                "comment_num": post["replyCount"],
                "last_comment_user": post["last"],
                "last_comment_time": post["replyTime"],
                "title": post["title"],
                "markdown_content": "",
                "add_time": "",
                "update_time": None
            }

            ret.append(topic_obj)

        return ret;

class Article(BasePage):
    def v2ex_json(self):
        data = self.response_.json()["data"]

        topic_obj = {
            "category": {
                "code": data["board"]["name"],
                "name": data["board"]["description"],
            },
            "author": {
                "username": data["head"]["poster"]["id"],
                "user": data["head"]["poster"]["user_name"],
                "avatar": data["head"]["poster"]["face_url"]
            },
            "topic_sn": "",
            "click_num": 0,
            "comment_num": None,
            "last_comment_user": "",
            "last_comment_time": None,
            "title": data["title"],
            "markdown_content": data["articles"][0]["content"].replace(' src="/', ' src="https://bbs.byr.cn/').replace(' href="/', ' href="https://bbs.byr.cn/'),
            "add_time": data["head"]["time"],
            "update_time": None
        }

        topic_obj["like_num"] = data["articles"][0].get("voteup_count", "0")
        topic_obj["dislike_num"] = data["articles"][0].get("votedown_count", "0")
        topic_obj["favorite_num"] = 0
        topic_obj["thanks"] = 0 
        topic_obj["page_count"] = data["pagination"]["total"]
        return topic_obj

    def v2ex_comments_obj(self):
        data = self.response_.json()["data"]
        current_page = int(data["pagination"]["current"])

        if current_page == 1:
            articles = data["articles"][1:]
        else:
            articles = data["articles"]
        ret = List()

        for index, article in enumerate(articles, start=1):
            comment = {
                "author": {
                    "username": article["poster"]["id"],
                    "user": article["poster"]["user_name"],
                    "avatar": article["poster"]["face_url"]
                },
                "id": article["id"],
                "add_time": article["time"],
                "content": article["content"],

                "badge": article["pos"]
            }
            ret.append(comment)

        total_page = int(data["pagination"]["total"])
        if total_page == 1:
            ret.count = len(articles)
            ret.last_comment_time = articles[-1]["time"] if len(articles) > 0 else None
        elif current_page == total_page:
            ret.count = int(articles[-1]["pos"])
            ret.last_comment_time = articles[-1]["time"]
        else:
            ret.count = str((total_page-1) * 10) + '+'
            ret.last_comment_time = "现在"


        return ret



class TimeLine(BasePage):
    def v2ex_json(self):
        ret = []

        for article in self.response_.json()["data"]["article"]:
            topic_obj = {
                "category": {
                    "code": article["board_name"],
                    "name": article["board_description"],
                },
                "author": {
                    "username": article["user"]["id"],
                    "user": article["user"]["user_name"],
                    "avatar": article["user"]["face_url"]
                },
                "topic_sn": article["board_name"]+"_"+str(article["id"]),
                "click_num": 0,
                "comment_num": None,
                "last_comment_user": "",
                "last_comment_time": None,
                "title": article["title"],
                "markdown_content": article["content"],
                "add_time": datetime.fromtimestamp(article["post_time"]).isoformat(),
                "update_time": None
            }

            ret.append(topic_obj)

        return ret;

class List(list):
    pass

class ByrApi:
    def __init__(self, username=None, password=None, storage=SpiderStorage("./session.dat")):
        self.sess_ = requests.session()
        # self.sess_.proxies = {"https": "127.0.0.1:10809"}
        self.storage_ = storage
        cookies = self.storage_.get("cookies")
        if not cookies:
            # self.sess_.post('https://bbs.byr.cn/n/b/auth/login.json', data={"username": username,"password": password})
            self.storage_["cookies"] = dict(self.sess_.cookies)
        else:
            self.sess_.cookies.update(cookies)
        self.timeout = 60

    def timeline(self, page):
        """
        获取时间轴的数据
        """
        return TimeLine(self.sess_.get('https://bbs.byr.cn/n/b/home/timeline.json?page=%d' % page, timeout=self.timeout))

    def topten(self):
        """
        获取十大内容
        """
        return TopTen(self.sess_.get('https://bbs.byr.cn/n/b/home/topten.json', timeout=self.timeout))

    def sections(self):
        """
        获取所有分区信息
        """
        return Sections(self.sess_.get('https://bbs.byr.cn/n/b/section.json', timeout=self.timeout))

    def section(self, board_id, page=1):
        """
        获取版面目录数据
        """
        return Section(self.sess_.get('https://bbs.byr.cn/n/b/board/%s.json?page=%d' % (board_id, page), timeout=self.timeout))

    def article(self, board_id, article_id, page=1):
        """
        获取文章
        """
        url = 'https://bbs.byr.cn/n/b/article/%s/%d.json?page=%d' % (board_id, article_id, page)

        r = self.sess_.get(url, timeout=self.timeout)
        return Article(r)

    def get_category(self):
        ret = List([
            {'code': 'hot', 'name': '十大'}, 
            {'code': '0', 'name': '站务'}, 
            {'code': '1', 'name': '校园'}, 
            {'code': '2', 'name': '学术'}, 
            {'code': '3', 'name': '社会'}, 
            {'code': '4', 'name': '艺术'}, 
            {'code': '5', 'name': '时尚'}, 
            {'code': '6', 'name': '娱乐'}, 
            {'code': '7', 'name': '健身'}, 
            {'code': '8', 'name': '游戏'}, 
            {'code': '9', 'name': '乡亲'}]
        )

        ret.hot = True
        return ret;

    def get_subcategory(self, tab, sub=None):
        sections = self.storage_.get("sections")
        if not sections:
            sections = self.sections().response_.json()
            self.storage_["sections"] = sections

        tab = int(tab)
        children = sections["data"]["boards"][tab]["children"]
        if sub is not None:
            children = children[int(sub)]["children"]

            

        topic_obj_list = List()
        category_children_obj = []
        
        for index, topic in enumerate(children):
            if topic["dir"]:
                category_children_obj.append({
                        "code": int(index),
                        "name": topic["name"],
                    })
            else:
                topic_obj = {
                    "category": {
                        "code": topic["id"],
                        "name": topic["id"],
                    },
                    "author": {
                        "username": topic["id"],
                        "user": topic["id"],
                        "avatar": ""
                    },
                    "topic_sn": topic["id"],
                    "click_num": 0,
                    "comment_num": topic["new"],
                    "last_comment_user": "",
                    "last_comment_time": None,
                    "title": topic["name"],
                    "markdown_content": topic["id"],
                    "add_time": None,
                    "update_time": None
                }

                topic_obj_list.append(topic_obj)

        topic_obj_list.hot = False

        return category_children_obj, topic_obj_list;



