import os
import re
import sys
import html
import json
import signal
import crayons
import requests
import feedparser
import configparser
import basc_py4chan as fch
import better_exceptions

from time import sleep
from collections import deque
from datetime import datetime

# init config and stuff
better_exceptions.MAX_LENGTH = None
config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini'))
watching = deque('')
leaks = deque('', 20)
cn_schedule = deque('', 20)
zap_schedule = deque('', 20)
cntumblr = deque('', 50)
crewniverse = deque('', 50)
cnarchive = deque('', 50)
geekiary = deque('', 50)
dhn = deque('', 50)
firstrun = True
ignore_until = 0
proxy_img = ''  # 'https://proxy.sug.rocks/'

# init 4chan boards
co = fch.Board('co', True)
trash = fch.Board('trash', True)


class TimeoutException(Exception):
    # Custom exception class
    pass


def timeout_handler(signum, frame):
    # Custom signal handler
    raise TimeoutException


def del_file(filename):
    try:
        os.remove(filename)
    except OSError:
        pass


def roll_color(postid):
    last = int(str(postid)[-1:])
    if last == 1:
        return 7999  # navy
    elif last == 2:
        return 29913  # blue
    elif last == 3:
        return 3066944  # green
    elif last == 4:
        return 3787980  # teal
    elif last == 5:
        return 8379391  # aqua
    elif last == 6:
        return 8721483  # maroon
    elif last == 7:
        return 11603401  # purple
    elif last == 8:
        return 14540253  # silver
    elif last == 9:
        return 16728374  # red
    else:
        return 16745755  # orange


def markdownify(text, post=None):
    # replace links
    if post:
        text = text.replace('href="#', 'href="' + post._thread.url + '/#')
    text = text.replace('href="/', 'href="https://boards.4chan.org/')
    # replace spoilers tags by something "working"
    text = text.replace('<s>', '[(⚠spoiler)[').replace('</s>', ']]')
    # replace italics
    text = text.replace('<i>', '_').replace('</i>', '_').replace('<em>', '_').replace('</em>', '_')
    # replace blockquote and new lines
    text = text.replace('</blockquote>', '</blockquote>\n')
    text = re.sub(r'<br.*?>', '\n', text)
    # replace links to markdown links
    text = re.sub(r'<a href=\"(.*)\" class=\"quotelink\">&gt;&gt;([0-9]*)</a>', r'[>>\2](\1) ', text)
    # remove any other html stuff and return
    return html.unescape(re.sub(r'<.*?>', '', text))


def find_first_image(description_html, default_img=None):
    img_regex = r"<img\b[^>]+?src\s*=\s*['\"]?([^\s'\"?#>]+)"
    img_matches = re.search(img_regex, description_html)

    if img_matches is not None:
        return img_matches.groups()[0]

    return default_img


def post_discord(params, cat, hook, upfile=None):
    # post to Discord
    global ignore_until
    # init
    filepath = ''
    r = None
    signal.alarm(20)

    # set content to json and use a 'normal' UA
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (compatible; sug/1.0)'
    }
    # build our webhook url
    url = "https://discordapp.com/api/webhooks/%s/%s" % (hook, config.get(cat, hook))

    try:
        # make the request
        if upfile:
            filepath = 'tmp/' + upfile['name']
            postfile = requests.get(upfile['url'], headers={'referer': 'https://boards.4chan.org'}, stream=True)
            with open(filepath, 'wb') as fd:
                for chunk in postfile.iter_content(chunk_size=128):
                    fd.write(chunk)
            with open(filepath, 'rb') as f:
                r = requests.post(url, data=params, files={'file': f})
        else:
            r = requests.post(url, data=params, headers=headers)
    except TimeoutException:
        pass  # Alarm rang
    except Exception as e:
        # try one more time
        try:
            print(crayons.yellow('\nPOSTing to Discord failed, will retry...'))
            print(e)
            sleep(3)
            if upfile:
                with open(filepath, 'rb') as f:
                    r = requests.post(url, data=params, files={'file': f})
            else:
                r = requests.post(url, data=params, headers=headers)
        except Exception as e:
            # give up
            print(crayons.red('POSTing to Discord failed again...\n'))
            print(e)
            # remove our file
            del_file(filepath)
            return

    if r is not None:
        if r.status_code != requests.codes.ok and r.status_code != 204:
            print('\nError with ' + str(params))
            print(crayons.red(r.text))

            try:
                j = r.json()
                if hasattr(j, 'message'):
                    if j['message'] == 'You are being rate limited.':
                        # too many posts, we'll wait until it's good + 10 secure seconds
                        ignore_until = int(datetime.now().timestamp()) + j['retry_after'] + 10
            except:
                pass

    del_file(filepath)


def push_thread(thread, edition=''):
    # if no edition found, just return "/sug/" and the thread number
    if edition == '':
        edition = '/sug/ no.' + str(thread.topic.post_id)

    # to make it easier
    post = thread.topic

    # default
    pushimg = False
    image = {}
    footer = {}

    if post.file.file_extension != 'webm' and not (hasattr(post, 'spoiler') and post.spoiler):
        # if there's an image and it's not spoiler, add it
        image = {
            'url': proxy_img + post.file.file_url
        }
        pushimg = True
    elif post.file.file_extension == 'webm':
        # if it's a webm, add a note about that
        footer = {
            'text': '(A webm is attached)',
            'icon_url': 'https://s.kdy.ch/4ch-warning.png'
        }
    elif hasattr(post, 'spoiler') and post.spoiler:
        # if it was spoiled, add a note about that
        footer = {
            'text': '(Image is spoiled)',
            'icon_url': 'https://s.kdy.ch/4ch-warning.png'
        }

    # and now we build the data to POST
    data = {
        'content': 'New thread on /' + thread._board.name + '/',
        'embeds': [
            {
                'title': edition,
                'color': roll_color(post.post_id),
                'url': thread.url,
                'timestamp': post.datetime.isoformat(),
                'footer': footer,
                'image': image
            }
        ]
    }

    # we dump that
    params = json.dumps(data).encode('utf8')

    # and we push to every concerned webhooks
    for hook in dict(config.items('newthread')):
        post_discord(params, 'newthread', hook)

    # if this post has an image, push to image-only channels
    if pushimg:
        filepost = {'name': post.file.filename, 'url': proxy_img + post.file.file_url}
        data = {
            'content': '[>>%s](<%s>)' % (post.post_id, post.url)
        }

        for hook in dict(config.items(thread._board.name + 'img')):
            post_discord(data, thread._board.name + 'img', hook, filepost)


def push_post(posts, edition=''):
    # if no edition found, just return "/sug/" and the thread number
    if edition == '':
        edition = '/sug/' + str(posts[0]._thread.topic.post_id)

    # will contain all our embeds
    embeds = []

    for post in posts:
        # default
        pushimg = False
        image = {}

        if post.has_file and post.file.file_extension != 'webm' and not (hasattr(post, 'spoiler') and post.spoiler):
            # if there's an image and it's not spoiler, add it
            image = {
                'url': proxy_img + post.file.file_url
            }
            footer = {
                'text': '📷(image) - ' + edition
            }
            pushimg = True
        elif post.has_file and post.file.file_extension == 'webm':
            # if it's a webm, add a note about that
            footer = {
                'text': '🎞 (webm) - ' + edition,
                'icon_url': 'https://s.kdy.ch/4ch-warning.png'
            }
        elif hasattr(post, 'spoiler') and post.spoiler:
            # if it was spoiled, add a note about that
            footer = {
                'text': '(Image is spoiled) - ' + edition,
                'icon_url': 'https://s.kdy.ch/4ch-warning.png'
            }
        else:
            footer = {
                'text': edition
            }

        embed = {
            'title': 'No.%d' % post.post_id,
            'description': markdownify(post.comment, post),
            'color': roll_color(post.post_id),
            'timestamp': post.datetime.isoformat(),
            'url': post.url,
            'footer': footer,
            'thumbnail': image
        }

        embeds.append(embed)

        # if this post has an image, push to image-only channels
        if pushimg and ignore_until < int(datetime.now().timestamp()):
            filepost = {'name': post.file.filename, 'url': proxy_img + post.file.file_url}
            data = {
                'content': '[>>%s](%s)' % (post.post_id, post.url)
            }

            for hook in dict(config.items(post._thread._board.name + 'img')):
                sleep(1)
                post_discord(data, post._thread._board.name + 'img', hook, filepost)

    # and now we build the data to POST
    data = {
        'embeds': embeds
    }

    # we dump that
    params = json.dumps(data).encode('utf8')

    # and we push to every concerned webhooks
    # if we're being rate limited, just ignore
    if ignore_until < int(datetime.now().timestamp()):
        for hook in dict(config.items(post._thread._board.name)):
            post_discord(params, post._thread._board.name, hook)


def check_cntumblr():
    # get CN tumblr feed about Steven Universe
    global cntumblr
    signal.alarm(20)

    try:
        r = requests.get('http://feeds.feedburner.com/tumblr/peLz')
        feed = feedparser.parse(r.text)

        for item in feed.entries:
            if not hasattr(item, 'tags'):
                continue
            if item.id not in cntumblr and any('steven universe' in tag.term for tag in item.tags):
                data = {
                    'username': feed.feed.title,
                    'avatar_url': 'https://sug.rocks/img/feeds/CN.jpg',
                    'embeds': [
                        {
                            'title': 'New post on Tumblr',
                            'description': markdownify(item.description),
                            'url': item.link,
                            'timestamp': datetime(*item.published_parsed[:-3]).isoformat()
                        }
                    ]
                }

                print(crayons.green('Tumblr CN: ' + item.title))

                params = json.dumps(data).encode('utf8')

                # and we push to every concerned webhooks
                if not firstrun:
                    for hook in dict(config.items('news')):
                        post_discord(params, 'news', hook)

                cntumblr.append(item.id)
    except TimeoutException:
        pass  # Alarm rang


def check_crewniverse():
    # get crewniverse tumblr feed
    global crewniverse
    signal.alarm(20)

    try:
        r = requests.get('http://feeds.feedburner.com/tumblr/xSqE')
        feed = feedparser.parse(r.text)

        for item in feed.entries:
            if item.id not in crewniverse:
                data = {
                    'username': 'Steven Crewniverse',
                    'avatar_url': 'https://sug.rocks/img/feeds/Crewniverse.png',
                    'embeds': [
                        {
                            'title': 'New post on Tumblr',
                            'description': markdownify(item.description),
                            'url': item.link,
                            'timestamp': datetime(*item.published_parsed[:-3]).isoformat()
                        }
                    ]
                }

                print(crayons.green('Tumblr Crew: ' + item.title))

                params = json.dumps(data).encode('utf8')

                # and we push to every concerned webhooks
                if not firstrun:
                    for hook in dict(config.items('news')):
                        post_discord(params, 'news', hook)

                crewniverse.append(item.id)
    except TimeoutException:
        pass  # Alarm rang


def check_cnarchive():
    # get CN Archive tumblr feed about Steven Universe
    global cnarchive
    signal.alarm(20)

    try:
        r = requests.get('http://feeds.feedburner.com/CNScheduleArchive')
        feed = feedparser.parse(r.text)

        for item in feed.entries:
            if not hasattr(item, 'tags'):
                continue
            if item.id not in cnarchive and any('Cartoon Network' in tag.term for tag in item.tags):
                data = {
                    'username': feed.feed.title,
                    'avatar_url': 'https://sug.rocks/img/feeds/CNArchive.png',
                    'embeds': [
                        {
                            'title': 'Schedule published',
                            'description': markdownify(item.title),
                            'url': item.link,
                            'timestamp': datetime(*item.published_parsed[:-3]).isoformat(),
                            'image': {
                                'url': find_first_image(item.description, 'https://sug.rocks/img/feeds/CNArchive.png')
                            }
                        }
                    ]
                }

                print(crayons.green('Tumblr Archive: ' + item.title))

                params = json.dumps(data).encode('utf8')

                # and we push to every concerned webhooks
                if not firstrun:
                    for hook in dict(config.items('news')):
                        post_discord(params, 'news', hook)

                cnarchive.append(item.id)
    except TimeoutException:
        pass  # Alarm rang


def check_geekiary():
    # get geekiary feed for Steven Universe
    global geekiary
    signal.alarm(20)

    try:
        r = requests.get('http://thegeekiary.com/tag/steven-universe/feed')
        feed = feedparser.parse(r.text)

        for item in feed.entries:
            if item.id not in geekiary:
                data = {
                    'username': 'The Geekiary',
                    'avatar_url': 'https://sug.rocks/img/feeds/geekiary.png',
                    'embeds': [
                        {
                            'title': item.title,
                            'description': markdownify(item.description.split('\n')[0]),
                            'url': item.link,
                            'timestamp': datetime(*item.published_parsed[:-3]).isoformat()
                        }
                    ]
                }

                print(crayons.green('Geekiary: ' + item.title))

                params = json.dumps(data).encode('utf8')

                # and we push to every concerned webhooks
                if not firstrun:
                    for hook in dict(config.items('news')):
                        post_discord(params, 'news', hook)
                        pass

                geekiary.append(item.id)
    except TimeoutException:
        pass  # Alarm rang


def check_dhn():
    # get Derpy Hooves News feed for Steven Universe
    global dhn
    signal.alarm(20)

    try:
        r = requests.get('http://sun.derpynews.com/feed/')
        feed = feedparser.parse(r.text)

        for item in feed.entries:
            if item.id not in dhn:
                data = {
                    'username': 'Derpy Hooves News',
                    'avatar_url': 'https://sug.rocks/img/feeds/dhn.png',
                    'embeds': [
                        {
                            'title': item.title,
                            'description': markdownify(item.description),
                            'url': item.link,
                            'timestamp': datetime(*item.published_parsed[:-3]).isoformat()
                        }
                    ]
                }

                print(crayons.green('DHN: ' + item.title))

                params = json.dumps(data).encode('utf8')

                # and we push to every concerned webhooks
                if not firstrun:
                    for hook in dict(config.items('news')):
                        post_discord(params, 'news', hook)

                dhn.append(item.id)
    except TimeoutException:
        pass  # Alarm rang


def check_leaks():
    # get leaks from sug.rocks
    global leaks, firstrun
    signal.alarm(20)

    try:
        r = requests.get('https://api.sug.rocks/leaks.json')
        cont = r.json()

        for item in cont:
            # for every leaks
            if item['id'] not in leaks:
                if len(item['images']) > 0:
                    image = {
                        'url': item['images'][0]['url'],
                    }
                else:
                    image = {}

                data = {
                    'content': 'The leakbot found something! Get everything on the [leaks page](https://sug.rocks/leaks.html).',
                    'embeds': [
                        {
                            'title': item['title'],
                            'description': markdownify(item['desc']),
                            'url': 'https://sug.rocks/leaks.html',
                            'timestamp': datetime.fromtimestamp(item['date']).isoformat(),
                            'image': image
                        }
                    ]
                }

                params = json.dumps(data).encode('utf8')

                # and we push to every concerned webhooks
                if not firstrun:
                    for hook in dict(config.items('leaks')):
                        post_discord(params, 'leaks', hook)

                leaks.append(item['id'])
    except TimeoutException:
        pass  # Alarm rang


def check_schedule():
    # get schedule from sug.rocks
    global cn_schedule, zap_schedule, firstrun
    signal.alarm(20)

    try:
        r = requests.get('https://api.sug.rocks/schedule.json')
        cont = r.json()

        for item in cont['cn']:
            # for every episode in CN schedule
            # generate a unique hash that won't repost the same schedule
            # beacause they just changed the order in the block
            title_words = ' '.join(sorted(item['title'].replace('/', ' ').lower().split()))

            if title_words not in cn_schedule:
                print(crayons.green(item['date'] + ' ' + item['time'] + ': ' + item['title']))
                data = {
                    'username': 'Cartoon Network schedule updates',
                    'avatar_url': 'https://sug.rocks/img/feeds/CN.jpg',
                    'embeds': [
                        {
                            'title': item['title'],
                            'fields': [
                                {
                                    'name': 'Air date',
                                    'value': item['date'],
                                    'inline': True
                                },
                                {
                                    'name': 'Air time',
                                    'value': item['time'],
                                    'inline': True
                                }
                            ]
                        }
                    ]
                }

                params = json.dumps(data).encode('utf8')

                # and we push to every concerned webhooks
                if not firstrun:
                    for hook in dict(config.items('schedule')):
                        post_discord(params, 'schedule', hook)

                cn_schedule.append(title_words)

        for item in cont['zap']:
            if item['id'] not in zap_schedule:  # don't double-post if nothing changes
                print(crayons.green(item['date'] + ': [' + item['episode'] + '] ' + item['title']))
                synopsis = '_None_'
                if item['synopsis'] is not None:
                    synopsis = item['synopsis']

                data = {
                    'username': 'Zap2It updates',
                    'avatar_url': 'http://tvlistings.zap2it.com/favicon.ico',
                    'embeds': [
                        {
                            'title': item['title'],
                            'fields': [
                                {
                                    'name': 'Air date',
                                    'value': item['date'],
                                    'inline': True
                                },
                                {
                                    'name': 'Episode Number',
                                    'value': item['episode'],
                                    'inline': True
                                },
                                {
                                    'name': 'Synopsis',
                                    'value': synopsis,
                                    'inline': False
                                }
                            ]
                        }
                    ]
                }

                params = json.dumps(data).encode('utf8')

                # and we push to every concerned webhooks
                if not firstrun:
                    for hook in dict(config.items('schedule')):
                        post_discord(params, 'schedule', hook)

                zap_schedule.append(item['id'])
    except TimeoutException:
        pass  # Alarm rang


def check_sug():
    # get data from sug.rocks about current /sug/ threads
    global firstrun
    signal.alarm(20)

    try:
        # fetch our json
        r = requests.get('https://api.sug.rocks/threads.json')
        cont = r.json()

        # for every /co/sug/ thread
        for i in cont['co']:
            item = cont['co'][i]
            try:
                # if not archived and that we don't have it yet
                if not item['status']['closed'] and not any(x['id'] == item['id'] for x in watching):
                    thread = co.get_thread(item['id'], False, True)
                    # add the thread and some infos to our deque
                    print(crayons.green('\nAdded: ' + item['edition']))
                    watching.append({'id': item['id'], 'edition': item['edition'], 'thread': thread})

                    # if it's not the first run of the script, push to concerned webhooks
                    if not firstrun:
                        push_thread(thread, item['edition'])
            except:
                print('huho co ' + str(i))
                pass

        # for every /trash/sug/ thread
        for i in cont['trash']:
            item = cont['trash'][i]
            try:
                # if not archived and that we don't have it yet
                if not item['status']['closed'] and not any(x['id'] == item['id'] for x in watching):
                    thread = trash.get_thread(item['id'], False, True)
                    # add the thread and some infos to our deque
                    print(crayons.green('\nAdded: ' + item['edition']))
                    watching.append({'id': item['id'], 'edition': item['edition'], 'thread': thread})

                    # if it's not the first run of the script, push to concerned webhooks
                    if not firstrun:
                        push_thread(thread, item['edition'])
            except:
                print('huho trash ' + str(i))
                pass

        # once done, it's not the first run anymore
        firstrun = False
    except TimeoutException:
        pass  # Alarm rang


def check_threads():
    toremove = []
    signal.alarm(20)

    try:
        for w in watching:
            # update saved threads, returns how many new posts we have
            upcount = w['thread'].update()
            if not hasattr(w['thread'], 'topic'):
                # if there isn't any 'topic' attribute, that means the thread is dead
                toremove.append(w)
                print(crayons.yellow('\n' + str(w['id']) + ' will be removed'))
            else:
                # if there's any new posts
                if upcount > 0:
                    # get them and push to concerned webhooks
                    sys.stdout.write('\r[{}] {}: {} new posts'.format(
                        crayons.blue(str(datetime.now())), str(w['id']), str(upcount)))
                    newposts = w['thread'].all_posts[-upcount:]
                    push_post(newposts, w['edition'])

        # remove dead threads from the main deque
        for r in toremove:
            watching.remove(r)
    except TimeoutException:
        pass  # Alarm rang


if __name__ == '__main__':
    relconf = 0

    while True:
        # always loop
        signal.signal(signal.SIGALRM, timeout_handler)

        if relconf > 60:
            # reload our config if needed
            config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini'))
            relconf = 0

        if relconf % 5 == 0:
            # check_leaks()
            # check_schedule()
            check_cntumblr()
            check_crewniverse()
            check_cnarchive()
            check_geekiary()
            check_dhn()

        check_sug()  # check current /sug/ threads
        check_threads()  # get the threads and new posts
        relconf += 1  # increment that, for reload the config

        signal.alarm(0)
        sleep(10)  # wait before poking everything again
