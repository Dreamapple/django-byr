from datetime import datetime
import markdown
import bleach
from extra.bleach_whitelist import markdown_tags, markdown_attrs
from django.shortcuts import render, redirect, HttpResponse
from django.urls import reverse
from django.db.models import F
from django.views.generic import View
from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from utils.auth_decorator import login_auth
from django.http import Http404
from utils.some_utils import gender_topic_sn
from utils.pagination import Paginator
from utils.update_balance import update_balance
from .models import TopicCategory, Topic, NodeLink, Comments
from operation.models import TopicVote, FavoriteNode
from user.models import UserFollowing
from .forms import NewTopicForm, MarkdownPreForm, CheckNodeForm
from django.core import serializers

from byr_api.byr_api import ByrApi

User = get_user_model()

api = ByrApi()



# Create your views here.

exts = ['markdown.extensions.extra', 'markdown.extensions.codehilite', 'markdown.extensions.tables',
        'markdown.extensions.toc']


class IndexView(View):
    def get(self, request):
        current_tab = request.GET.get('tab', 'hot')
        category_obj = api.get_category()
        if current_tab == 'hot':
            topic_obj = api.topten().v2ex_json()
            return render(request, 'topic/index.html', locals())
        else:
            sub = request.GET.get('sub')
            category_children_obj, topic_obj = api.get_subcategory(current_tab, sub)
            if len(category_children_obj) > 0:
                category_obj.hot = False
            return render(request, 'topic/tab.html', locals())
        


class NewTopicView(View):
    @method_decorator(login_auth)
    def dispatch(self, request, *args, **kwargs):
        return super(NewTopicView, self).dispatch(request, *args, **kwargs)

    def get(self, request):
        obj = CheckNodeForm(request.GET)
        if obj.is_valid():
            topic_node_code = obj.cleaned_data['topic_node_code']
            node_obj = TopicCategory.objects.filter(code=topic_node_code, category_type=2).first()
            return render(request, 'topic/new.html', locals())
        node_obj = TopicCategory.objects.filter(category_type=2)
        return render(request, 'topic/new.html', locals())

    def post(self, request):
        has_error = True
        obj = NewTopicForm(request.POST)
        if obj.is_valid():
            has_error = False
            title = obj.cleaned_data['title']
            content = obj.cleaned_data['content']
            topic_node = obj.cleaned_data['topic_node']
            # ?????????????????????
            topic_sn = gender_topic_sn()
            # ??????xss markdown??????
            title = bleach.clean(title)
            markdown_content = markdown.markdown(content, format="xhtml5", extensions=exts)
            markdown_content = bleach.clean(markdown_content, tags=markdown_tags, attributes=markdown_attrs)
            # ??????
            topic_obj = Topic.objects.create(author_id=request.session.get('user_info')['uid'], title=title,
                                             markdown_content=markdown_content,
                                             category_id=topic_node,
                                             topic_sn=topic_sn)

            # ??????F ??????????????? ??????Topic ?????????node ????????????
            TopicCategory.objects.filter(id=topic_node, category_type=2).update(count_topic=F('count_topic') + 1)

            # ?????????????????????
            update_balance(request, update_type='create', obj=topic_obj)
            return redirect(reverse('topic', args=(topic_sn,)))
        node_obj = TopicCategory.objects.filter(category_type=2)
        return render(request, 'topic/new.html', locals())


class RecentView(View):
    # @method_decorator(login_auth)
    # def dispatch(self, request, *args, **kwargs):
    #     return super(RecentView, self).dispatch(request, *args, **kwargs)

    def get(self, request):
        current_page = request.GET.get('p', '1')
        current_page = int(current_page)
        topic_obj = api.timeline(current_page).v2ex_json()
        page_obj = Paginator(current_page, 600)
        page_str = page_obj.page_str(reverse('recent') + '?')
        return render(request, 'topic/recent.html', locals())


class NodeView(View):
    def get(self, request, node_code):
        current_page = request.GET.get('p', '1')
        current_page = int(current_page)
        try:
            node = api.section(node_code, current_page)
            node_obj = node.v2ex_node_obj()
            topic_obj = node.v2ex_topic_obj()

            # node_obj = TopicCategory.objects.get(code=node_code, category_type=2)
            # if request.session.get('user_info'):
            #     node_obj["favorite"] = FavoriteNode.objects.values_list('favorite').filter(
            #         user_id=request.session.get('user_info')['uid'],
            #         node=node_obj).first()
            # topic_obj = Topic.objects.select_related('author', 'category').filter(category=node_obj).order_by('-add_time')
            page_obj = Paginator(current_page, node_obj["total"]*30)
            param = reverse('node', args=(node_code,)) + '?'
            page_str = page_obj.page_str(param)
            return render(request, 'topic/node.html', locals())
        except TopicCategory.DoesNotExist:
            raise Http404("node does not exist")


class NodeLinkView(View):
    def get(self, request, node_code):
        current_page = request.GET.get('p', '1')
        current_page = int(current_page)
        try:
            node_obj = TopicCategory.objects.get(code=node_code, category_type=2)
            if request.session.get('user_info'):
                node_obj.favorite = FavoriteNode.objects.values_list('favorite').filter(
                    user_id=request.session.get('user_info')['uid'],
                    node=node_obj).first()
            node_link_obj = NodeLink.objects.select_related('author').filter(
                category=node_obj).order_by('-add_time')
            page_obj = Paginator(current_page, node_link_obj.count())
            node_link_obj = node_link_obj[page_obj.start:page_obj.end]
            page_str = page_obj.page_str(reverse('node_link', args=(node_code,)) + '?')
            return render(request, 'topic/node_link.html', locals())
        except TopicCategory.DoesNotExist:
            raise Http404("node does not exist")


class TopicView(View):
    def get(self, request, topic_sn):
        try:
            if '_' not in topic_sn:
                topic_obj = Topic.objects.get(topic_sn=topic_sn)
                # ??????????????????
                topic_obj.like_num = TopicVote.objects.filter(vote=1, topic=topic_obj).count()
                topic_obj.dislike_num = TopicVote.objects.filter(vote=0, topic=topic_obj).count()
                topic_obj.favorite_num = TopicVote.objects.filter(favorite=1, topic=topic_obj).count()
                comments_obj = Comments.objects.select_related('author').filter(topic=topic_obj)
                now = datetime.now()
                if request.session.get('user_info'):
                    topic_obj.thanks = TopicVote.objects.values_list('thanks').filter(topic=topic_obj,
                                                                                      user_id=
                                                                                      request.session.get('user_info')[
                                                                                          'uid']).first()
                    topic_obj.favorite = TopicVote.objects.values_list('favorite').filter(topic=topic_obj,
                                                                                          user_id=
                                                                                          request.session.get('user_info')[
                                                                                              'uid']).first()
                # ??????F ??????????????? ????????????????????????
                Topic.objects.filter(topic_sn=topic_sn).update(click_num=F('click_num') + 1)
                return render(request, 'topic/topic.html', locals())
            else:
                current_page = request.GET.get('p', '1')
                current_page = int(current_page)
                board, gid = topic_sn.rsplit("_", 1)
                article_1 = api.article(board, int(gid), 1)
                topic_obj = article_1.v2ex_json()
                if current_page == 1:
                    comments_obj = article_1.v2ex_comments_obj()
                else:
                    article = api.article(board, int(gid), current_page)
                    comments_obj = article.v2ex_comments_obj()

                if request.session.get('user_info'):
                    topic_obj["thanks"] = TopicVote.objects.values_list('thanks').filter(topic_s=topic_sn,
                                                                                      user_id=
                                                                                      request.session.get('user_info')[
                                                                                          'uid']).first()
                    topic_obj["favorite"] = TopicVote.objects.values_list('favorite').filter(topic_s=topic_sn,
                                                                                          user_id=
                                                                                          request.session.get('user_info')[
                                                                                              'uid']).first()
               
                page_obj = Paginator(current_page, topic_obj["page_count"] * 10, 10)
                page_str = page_obj.page_str(reverse('topic', args=(topic_sn,)) + '?')
                return render(request, 'topic/topic.html', locals())

        except Topic.DoesNotExist:
            raise Http404("topic does not exist")

    @method_decorator(login_auth)
    def post(self, request, topic_sn):
        # todo ??????????????????
        content = request.POST.get('content', None)
        if content is not None:
            try:
                # topic_obj = Topic.objects.select_related('author_s').get(topic_sn=topic_sn)
                content = bleach.clean(content)
                comments_obj = Comments.objects.create(topic_s=topic_sn,
                                                       author_s=request.session.get('user_info')['uid'],
                                                       content=content)
                # ?????????????????????????????? ???????????????????????????????????????????????????
                # update_balance(request, update_type='reply', obj=topic_obj)
                return redirect(reverse('topic', args=(topic_sn,)))
            except Topic.DoesNotExist:
                raise Http404("topic does not exist")


class MarkdownPreView(View):
    @method_decorator(login_auth)
    def dispatch(self, request, *args, **kwargs):
        return super(MarkdownPreView, self).dispatch(request, *args, **kwargs)

    def post(self, request):
        obj = MarkdownPreForm(request.POST)
        if obj.is_valid():
            md = obj.cleaned_data['md']
            # ??????markdown??????
            md_html = markdown.markdown(md, format="xhtml5", extensions=exts)
            # ????????????????????????
            md_html = bleach.clean(md_html, tags=markdown_tags, attributes=markdown_attrs)
            return HttpResponse(md_html)

        return HttpResponse('')


class MyFavoriteNodeView(View):
    @method_decorator(login_auth)
    def dispatch(self, request, *args, **kwargs):
        return super(MyFavoriteNodeView, self).dispatch(request, *args, **kwargs)

    def get(self, request):
        my_favorite_obj = FavoriteNode.objects.select_related('node').filter(favorite=1,
                                                                             user_id=request.session.get('user_info')[
                                                                                 'uid']).order_by('-add_time')
        return render(request, 'topic/my_node.html', locals())


class MyFavoriteTopicView(View):
    @method_decorator(login_auth)
    def dispatch(self, request, *args, **kwargs):
        return super(MyFavoriteTopicView, self).dispatch(request, *args, **kwargs)

    def get(self, request):
        my_favorite_obj = TopicVote.objects.select_related('topic__author', 'topic__category').filter(
            favorite=1,
            user_id=request.session.get('user_info')['uid']).order_by('-add_time')

        return render(request, 'topic/my_topic.html', locals())


class MyFollowingView(View):
    @method_decorator(login_auth)
    def dispatch(self, request, *args, **kwargs):
        return super(MyFollowingView, self).dispatch(request, *args, **kwargs)

    def get(self, request):
        # ???????????????????????????????????????QuerySet  ?????? is_following  ????????? 1
        my_following_obj = UserFollowing.objects.select_related('following').filter(
            user_id=request.session.get('user_info')['uid'],
            is_following=1)

        # ????????????????????????????????????????????????????????????id
        following_user_id = []
        # ???id ????????????
        for obj in my_following_obj:
            following_user_id.append(obj.following.id)
        # ??????in????????????id??????????????????????????????
        following_topic_obj = Topic.objects.select_related('category', 'author').filter(
            author_id__in=following_user_id).order_by('-add_time')

        return render(request, 'topic/my_following.html', locals())
