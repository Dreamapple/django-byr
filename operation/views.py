import json
from datetime import datetime, timedelta, date
from django.shortcuts import HttpResponse, redirect, render
from django.urls import reverse
from django.http import Http404
from django.db.models import F
from django.views.generic import View
from django.utils.decorators import method_decorator
from utils.auth_decorator import login_auth
from .tasks import send_email_code
from utils.pagination import Paginator
from utils.some_utils import gender_random_code, save_avatar_file, gender_random_balance
from utils.update_balance import update_balance
from django.contrib.auth import get_user_model
from .models import Topic, TopicVote, FavoriteNode, TopicCategory, UserDetails, BalanceInfo, SignedInfo
from .forms import TopicVoteForm, CheckTopicForm, CheckNodeForm, SettingsForm, PhoneSettingsForm, EmailSettingsForm, \
    AvatarSettingsForm, PasswordSettingsForm
from user.models import UserFollowing, VerifyCode

User = get_user_model()


# Create your views here.


class TopicVoteView(View):
    @method_decorator(login_auth)
    def dispatch(self, request, *args, **kwargs):
        return super(TopicVoteView, self).dispatch(request, *args, **kwargs)

    def post(self, request):
        ret = {
            'changed': False,
            'topic_sn': '',
            'data': ''
        }
        obj = TopicVoteForm(request.POST)
        if obj.is_valid():
            ret['changed'] = True
            topic_sn = obj.cleaned_data['topic_sn']
            vote_action = obj.cleaned_data['vote_action']

            flag = 0
            if vote_action == 'up':
                flag = 1
            try:
                topic_vote_obj = TopicVote.objects.get(user_id=request.session.get('user_info')['uid'], topic_s=topic_sn)
                topic_vote_obj.vote = flag
                topic_vote_obj.save()
            except TopicVote.DoesNotExist:
                topic_vote_obj = TopicVote()
                topic_vote_obj.user_id = request.session.get('user_info')['uid']
                topic_vote_obj.vote = flag
                topic_vote_obj.topic_s = topic_sn
                topic_vote_obj.save()
            ret['topic_sn'] = topic_sn
            ret['data'] = '''
                <a href="javascript:" onclick="upVoteTopic('{_topic_sn}');" class="vote">
                <li class="fa fa-chevron-up">&nbsp;{_like_num}</li>
                </a> &nbsp;
                <a href="javascript:" onclick="downVoteTopic('{_topic_sn}');" class="vote">
                <li class="fa fa-chevron-down">&nbsp;{_dislike_num}</li>
                </a>
                '''.format(_like_num=TopicVote.objects.filter(vote=1, topic_s=topic_sn).count(),
                           _dislike_num=TopicVote.objects.filter(vote=0, topic_s=topic_sn).count(),
                           _topic_sn=topic_sn, )
        else:
            ret['changed'] = False
            ret['data'] = obj.errors.as_json()

        return HttpResponse(json.dumps(ret))


class FavoriteTopicView(View):
    @method_decorator(login_auth)
    def dispatch(self, request, *args, **kwargs):
        return super(FavoriteTopicView, self).dispatch(request, *args, **kwargs)

    def post(self, request):
        ret = {
            'changed': False,
            'topic_sn': '',
            'data': ''
        }
        obj = CheckTopicForm(request.POST)
        if obj.is_valid():
            ret['changed'] = True
            topic_sn = obj.cleaned_data['topic_sn']

            try:
                topic_vote_obj = TopicVote.objects.get(user_id=request.session.get('user_info')['uid'], topic_s=topic_sn)
                if topic_vote_obj.favorite == 1:
                    topic_vote_obj.favorite = 0
                    request.session['user_info']['favorite_topic_num'] -= 1
                    ret['data'] = "&nbsp;????????????&nbsp;"
                else:
                    topic_vote_obj.favorite = 1
                    request.session['user_info']['favorite_topic_num'] += 1
                    ret['data'] = "&nbsp;????????????&nbsp;"
                topic_vote_obj.save()
            except TopicVote.DoesNotExist:
                topic_vote_obj = TopicVote()
                topic_vote_obj.user_id = request.session.get('user_info')['uid']
                topic_vote_obj.favorite = 1
                topic_vote_obj.topic_s = topic_sn
                topic_vote_obj.save()
                request.session['user_info']['favorite_topic_num'] += 1
                ret['data'] = "&nbsp;????????????&nbsp;"
            ret['topic_sn'] = topic_sn
        else:
            ret['changed'] = False
            ret['data'] = obj.errors.as_json()

        ret = json.dumps(ret)
        print(ret)
        return HttpResponse(ret)


class ThanksTopicView(View):
    @method_decorator(login_auth)
    def dispatch(self, request, *args, **kwargs):
        return super(ThanksTopicView, self).dispatch(request, *args, **kwargs)

    def post(self, request):
        ret = {
            'changed': False,
            'topic_sn': '',
            'data': ''
        }
        obj = CheckTopicForm(request.POST)
        if obj.is_valid():
            ret['changed'] = True
            topic_sn = obj.cleaned_data['topic_sn']
            try:
                topic_obj = Topic.objects.select_related('author').filter(topic_sn=topic_sn).first()
            except DoesNotExist:
                # todo
                topic_obj = ByrFileAPI.get_topic(topic_sn)
            # ???????????????topic ????????????????????????
            if topic_obj.author_id != request.session.get('user_info')['uid']:
                try:
                    topic_vote_obj = TopicVote.objects.get(user_id=request.session.get('user_info')['uid'],
                                                           topic_s=topic_sn)
                    print(topic_vote_obj)
                    if topic_vote_obj.thanks == 1:
                        ret['changed'] = False
                    else:
                        topic_vote_obj.thanks = 1
                        topic_vote_obj.save()
                except TopicVote.DoesNotExist:
                    topic_vote_obj = TopicVote()
                    topic_vote_obj.user_id = request.session.get('user_info')['uid']
                    topic_vote_obj.thanks = 1
                    topic_vote_obj.topic_s = topic_sn
                    topic_vote_obj.save()
                    # ?????????????????????
                    update_balance(request, update_type='thanks', obj=topic_obj)
                    update_balance(request, update_type='recv_thanks', obj=topic_obj)
                ret['data'] = "&nbsp;??????????????????&nbsp;"
                ret['topic_sn'] = topic_sn
            else:
                ret['data'] = obj.errors.as_json()

        return HttpResponse(json.dumps(ret))


class FavoriteNodeView(View):
    @method_decorator(login_auth)
    def dispatch(self, request, *args, **kwargs):
        return super(FavoriteNodeView, self).dispatch(request, *args, **kwargs)

    def post(self, request):
        ret = {
            'changed': False,
            'node_code': '',
            'data': ''
        }
        obj = CheckNodeForm(request.POST)
        if obj.is_valid():
            ret['changed'] = True
            node_code = obj.cleaned_data['node_code']
            node_obj = TopicCategory.objects.filter(code=node_code, category_type=2).first()
            try:
                favorite_node_obj = FavoriteNode.objects.get(user_id=request.session.get('user_info')['uid'],
                                                             node=node_obj)
                if favorite_node_obj.favorite == 1:
                    favorite_node_obj.favorite = 0
                    request.session['user_info']['favorite_node_num'] -= 1
                    ret['data'] = "????????????"
                else:
                    favorite_node_obj.favorite = 1
                    request.session['user_info']['favorite_node_num'] += 1
                    ret['data'] = "????????????"
                favorite_node_obj.save()
            except FavoriteNode.DoesNotExist:
                favorite_node_obj = FavoriteNode()
                favorite_node_obj.user_id = request.session.get('user_info')['uid']
                favorite_node_obj.favorite = 1
                favorite_node_obj.node = node_obj
                favorite_node_obj.save()
                request.session['user_info']['favorite_node_num'] += 1
                ret['data'] = "????????????"
            ret['node_code'] = node_code
        else:
            ret['changed'] = False
            ret['data'] = obj.errors.as_json()

        return HttpResponse(json.dumps(ret))


class FollowingView(View):
    @method_decorator(login_auth)
    def dispatch(self, request, *args, **kwargs):
        return super(FollowingView, self).dispatch(request, *args, **kwargs)

    def get(self, request, username):
        if username == request.session.get('user_info')['username']:
            return redirect(reverse('member', args=(username,)))
        following_user_obj = User.objects.filter(username=username).first()
        if following_user_obj:
            try:
                following_obj = UserFollowing.objects.get(user_id=request.session.get('user_info')['uid'],
                                                          following=following_user_obj)
                if following_obj.is_following == 1:
                    following_obj.is_following = 0
                    request.session['user_info']['following_user_num'] -= 1
                else:
                    following_obj.is_following = 1
                    request.session['user_info']['following_user_num'] += 1
                following_obj.save()
            except UserFollowing.DoesNotExist:
                following_obj = UserFollowing()
                following_obj.user_id = request.session.get('user_info')['uid']
                following_obj.is_following = 1
                following_obj.following = following_user_obj
                following_obj.save()
                request.session['user_info']['following_user_num'] += 1
            return redirect(reverse('member', args=(username,)))
        else:
            raise Http404("will following user does not exist")


class BlockView(View):
    @method_decorator(login_auth)
    def dispatch(self, request, *args, **kwargs):
        return super(BlockView, self).dispatch(request, *args, **kwargs)

    def get(self, request, username):
        if username == request.session.get('user_info')['username']:
            return redirect(reverse('member', args=(username,)))
        block_user_obj = User.objects.filter(username=username).first()
        if block_user_obj:
            try:
                block_obj = UserFollowing.objects.get(user_id=request.session.get('user_info')['uid'],
                                                      following=block_user_obj)
                if block_obj.is_block == 1:
                    block_obj.is_block = 0
                else:
                    block_obj.is_block = 1
                block_obj.save()
            except UserFollowing.DoesNotExist:
                block_obj = FavoriteNode()
                block_obj.user_id = request.session.get('user_info')['uid']
                block_obj.is_block = 1
                block_obj.following = block_user_obj
                block_obj.save()
            return redirect(reverse('member', args=(username,)))
        else:
            raise Http404("will block user does not exist")


class SettingView(View):
    @method_decorator(login_auth)
    def dispatch(self, request, *args, **kwargs):
        return super(SettingView, self).dispatch(request, *args, **kwargs)

    def get(self, request):
        # ???????????????????????????
        user_detail_obj = UserDetails.objects.select_related('user').filter(
            user_id=request.session.get('user_info')['uid']).first()

        return render(request, 'user/settings.html', locals())

    def post(self, request):
        has_error = True
        # ??????
        obj = SettingsForm(request.POST)
        # ???????????????????????????
        user_detail_obj = UserDetails.objects.filter(user_id=request.session.get('user_info')['uid']).first()

        if obj.is_valid():
            has_error = False
            # ??????
            valid_data = obj.cleaned_data
            User.objects.filter(id=request.session.get('user_info')['uid']).update(location=valid_data['location'])
            valid_data.pop('location')
            user_detail_obj.__dict__.update(valid_data)
            user_detail_obj.save()
            # ??????Django ???????????????????????????????????????????????????????????????redis ?????????(?????????????????????????????????????????????????????????)
            request.session['user_info']['show_balance'] = int(valid_data['show_balance'])
        return render(request, 'user/settings.html', locals())


class PhoneSettingView(View):
    @method_decorator(login_auth)
    def dispatch(self, request, *args, **kwargs):
        return super(PhoneSettingView, self).dispatch(request, *args, **kwargs)

    def get(self, request):
        # ???????????????Phone
        user_obj = User.objects.filter(id=request.session.get('user_info')['uid']).first()
        return render(request, 'user/setting_phone.html', locals())

    def post(self, request):
        has_error = True
        # ??????
        obj = PhoneSettingsForm(request.POST)
        if obj.is_valid():
            password = obj.cleaned_data['password']
            new_phone_number = obj.cleaned_data['new_phone_number']
            user_obj = User.objects.filter(id=request.session.get('user_info')['uid']).first()
            if user_obj.check_password(password):
                user_obj.mobile = new_phone_number
                # ????????????????????????
                user_obj.mobile_verify = 1
                # ??????
                user_obj.save()
                has_error = False
            else:
                password_error = "????????????"
        return render(request, 'user/setting_phone.html', locals())


class EmailSettingView(View):
    @method_decorator(login_auth)
    def dispatch(self, request, *args, **kwargs):
        return super(EmailSettingView, self).dispatch(request, *args, **kwargs)

    def get(self, request):
        # ???????????????Email
        user_obj = User.objects.filter(id=request.session.get('user_info')['uid']).first()
        return render(request, 'user/setting_email.html', locals())

    def post(self, request):
        has_error = True
        # ??????
        obj = EmailSettingsForm(request.POST)
        user_obj = User.objects.filter(id=request.session.get('user_info')['uid']).first()
        if obj.is_valid():
            password = obj.cleaned_data['password']
            new_email = obj.cleaned_data['new_email']
            if user_obj.check_password(password):
                user_obj.email = new_email
                user_obj.email_verify = 0
                # ??????
                user_obj.save()
                # ???????????????
                random_code = gender_random_code()
                # ???????????? ??????id
                ret_obj = send_email_code.delay(to=new_email, code=random_code)
                # ???????????????
                code_obj = VerifyCode.objects.create(to=new_email, code_type=0, code=random_code)
                code_obj.code = random_code
                code_obj.task_id = ret_obj.task_id
                code_obj.save()
                has_error = False
            else:
                password_error = "????????????"
        return render(request, 'user/setting_email.html', locals())


class ActivateEmailView(View):
    def get(self, request, code):
        # ??????
        code_obj = VerifyCode.objects.filter(code=code, code_type=0).last()
        current_time = datetime.now()
        # ???????????????code???????????????????????????
        if code_obj and int((current_time - code_obj.add_time).total_seconds()) < 600:
            user_obj = User.objects.filter(email=code_obj.to).first()
            if user_obj:
                user_obj.email_verify = 1
                user_obj.save()
        return render(request, 'user/activate_email_code.html', locals())


class SendActivateCodeView(View):
    @method_decorator(login_auth)
    def post(self, request, ):
        ret = {
            'changed': False,
            'data': '60?????????'
        }
        send_type = request.POST.get('send_type', None)
        send_to = request.POST.get('send_to', None)
        if send_type and send_to:
            # ??????????????????????????????????????????????????????
            if User.objects.filter(email=send_to, email_verify=1).first():
                ret['changed'] = False
                ret['data'] = "????????????????????????"
                return HttpResponse(json.dumps(ret))

            random_code = gender_random_code()
            current_time = datetime.now()
            code_obj = VerifyCode.objects.filter(to=send_to, code_type=send_type).last()
            # ????????????????????????60???????????????????????????????????????????????????
            if not code_obj or int((current_time - code_obj.add_time).total_seconds()) > 60:
                ret_obj = send_email_code.delay(to=send_to, code=random_code)
                code_obj = VerifyCode.objects.create(to=send_to, code_type=send_type, code=random_code)
                code_obj.code = random_code
                code_obj.task_id = ret_obj.task_id
                code_obj.save()
                ret['changed'] = True
                ret['data'] = "????????????"

        return HttpResponse(json.dumps(ret))


class AvatarSettingView(View):
    @method_decorator(login_auth)
    def dispatch(self, request, *args, **kwargs):
        return super(AvatarSettingView, self).dispatch(request, *args, **kwargs)

    def get(self, request):
        # ??????
        user_obj = User.objects.filter(id=request.session.get('user_info')['uid']).first()
        return render(request, 'user/setting_avatar.html', locals())

    def post(self, request):
        has_error = True
        # ??????
        user_obj = User.objects.filter(id=request.session.get('user_info')['uid']).first()
        obj = AvatarSettingsForm(request.POST, request.FILES)
        if obj.is_valid():
            avatar = request.FILES['avatar']
            # ???????????????????????????2M?????????
            if avatar.size <= 2 * 1024 * 1024:
                avatar_path = save_avatar_file(avatar)
                user_obj.avatar = avatar_path
                # ??????
                user_obj.save()
                request.session['user_info']['avatar'] = user_obj.avatar
                has_error = False
            else:
                avatar_size_error = "????????????????????????2M"
        return render(request, 'user/setting_avatar.html', locals())


class PasswordSettingView(View):
    @method_decorator(login_auth)
    def dispatch(self, request, *args, **kwargs):
        return super(PasswordSettingView, self).dispatch(request, *args, **kwargs)

    def get(self, request):
        return redirect(reverse('settings'))

    def post(self, request):
        has_error = True
        user_obj = User.objects.filter(id=request.session.get('user_info')['uid']).first()
        # ??????
        obj = PasswordSettingsForm(request.POST)
        if obj.is_valid():
            password_current = obj.cleaned_data['password_current']
            password_new = obj.cleaned_data['password_new']
            password_again = obj.cleaned_data['password_again']
            # ???????????????????????????
            if user_obj.check_password(password_current):
                if password_new == password_again:
                    user_obj.set_password(password_new)
                    # ??????
                    user_obj.save()
                    has_password_error = False
                else:
                    password_error = "??????????????????????????????"
            else:
                password_error = "?????????????????????????????????"
        return render(request, 'user/setting_password.html', locals())


class DailyMissionView(View):
    @method_decorator(login_auth)
    def dispatch(self, request, *args, **kwargs):
        return super(DailyMissionView, self).dispatch(request, *args, **kwargs)

    def get(self, request):
        # ??????????????????
        current_date = datetime.now().strftime('%Y%m%d')
        # ????????????????????????
        signed_obj = SignedInfo.objects.filter(user_id=request.session.get('user_info')['uid'],
                                               date=current_date).first()
        # ?????????????????????????????????
        if signed_obj:
            signed_day = signed_obj.signed_day
        else:
            signed_day = 0
        return render(request, 'operation/daily_mission.html', locals())


class DailyRandomBalanceView(View):
    @method_decorator(login_auth)
    def dispatch(self, request, *args, **kwargs):
        return super(DailyRandomBalanceView, self).dispatch(request, *args, **kwargs)

    def get(self, request):
        # ??????????????????????????????
        if not request.session.get('user_info')['daily_mission']:
            # ??????????????????
            current_date = datetime.now().strftime('%Y%m%d')
            # ??????????????????
            random_balance = gender_random_balance()

            # ????????????????????????????????? ??????F
            UserDetails.objects.filter(user_id=request.session.get('user_info')['uid']).update(
                balance=F('balance') + random_balance)

            # ?????????????????????????????????
            user_obj = UserDetails.objects.filter(user_id=request.session.get('user_info')['uid']).first()

            # ????????????????????????
            BalanceInfo.objects.create(
                user_id=request.session.get('user_info')['uid'],
                balance_type="??????????????????",
                balance=random_balance,
                marks='{_date} ????????????????????? {_num} ??????'.format(_date=current_date, _num=random_balance),
                last_balance=user_obj.balance
            )

            # ??????session??????
            request.session['user_info']['daily_mission'] = True
            request.session['user_info']['balance'] = user_obj.balance

            # ???????????????????????????????????????????????????????????????????????????
            yesterday_date = (date.today() - timedelta(days=1)).strftime('%Y%m%d')

            # ????????????????????????
            signed_obj = SignedInfo.objects.filter(date=yesterday_date,
                                                   user_id=request.session.get('user_info')['uid']).first()

            if signed_obj:
                # ??????????????????????????????????????????????????????+1
                signed_day = signed_obj.signed_day + 1
            else:
                # ??????????????????????????????1
                signed_day = 1

            print("SignedInfo", request.session.get('user_info')['uid'], signed_day)

            # ??????????????????
            SignedInfo.objects.create(
                date=current_date,
                user_id=request.session.get('user_info')['uid'],
                status=True,
                signed_day=signed_day
            )

        return redirect(reverse('daily_mission'))


class BalanceView(View):
    @method_decorator(login_auth)
    def dispatch(self, request, *args, **kwargs):
        return super(BalanceView, self).dispatch(request, *args, **kwargs)

    def get(self, request):
        current_page = request.GET.get('p', '1')
        current_page = int(current_page)
        balance_info_obj = BalanceInfo.objects.filter(user_id=request.session.get('user_info')['uid']).order_by(
            '-add_time')
        page_obj = Paginator(current_page, balance_info_obj.count())
        balance_info_obj = balance_info_obj[page_obj.start:page_obj.end]
        page_str = page_obj.page_str(reverse('balance') + '?')
        return render(request, 'operation/balance.html', locals())
