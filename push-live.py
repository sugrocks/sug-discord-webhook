import os
import re
import sys
import html
import json
import crayons
import requests
import feedparser
import configparser
import basc_py4chan as fch

from time import sleep
from collections import deque
from datetime import datetime
from bs4 import BeautifulSoup

# init config and stuff
config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini'))
watching = deque('')
leaks = deque('', 20)
schedule = deque('', 20)
zap = deque('', 20)
cntumblr = deque('', 20)
firstrun = True

# init 4chan boards
co = fch.Board('co', True)
trash = fch.Board('trash', True)


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


def post_discord(params, cat, hook, upfile=None):
    # post to Discord
    # init
    filepath = ''

    # set content to json and use a 'normal' UA
    headers = {
        'content-type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (compatible; sug/1.0)'
    }
    # build our webhook url
    url = "https://discordapp.com/api/webhooks/%s/%s" % (hook, config.get(cat, hook))

    try:
        # make the request
        if upfile:
            filepath = 'tmp/' + upfile['name']
            postfile = requests.get(upfile['url'], stream=True)
            with open(filepath, 'wb') as fd:
                for chunk in postfile.iter_content(chunk_size=128):
                    fd.write(chunk)
            with open(filepath, 'rb') as f:
                r = requests.post(url, data=params, files={'file': f})
        else:
            r = requests.post(url, data=params, headers=headers)
    except:
        # try one more time
        try:
            print(crayons.yellow('\nPOSTing to Discord failed, will retry...'))
            sleep(3)
            if upfile:
                with open(filepath, 'rb') as f:
                    r = requests.post(url, data=params, files={'file': f})
            else:
                r = requests.post(url, data=params, headers=headers)
        except:
            # give up
            print(crayons.red('POSTing to Discord failed again...\n'))
            # remove our file
            del_file(filepath)
            return

    if r.status_code != requests.codes.ok:
        print(crayons.red(r.text))

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
            'url': post.file.file_url
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
        filepost = {'name': post.file.filename, 'url': post.file.file_url}
        data = {
            'content': '[>>%s](<%s>)' % (post.post_id, post.url)
        }

        for hook in dict(config.items(thread._board.name + 'img')):
            post_discord(data, thread._board.name + 'img', hook, filepost)


def push_post(post, edition=''):
    # if no edition found, just return "/sug/" and the thread number
    if edition == '':
        edition = '/sug/ no.' + str(post._thread.topic.post_id)

    # default
    pushimg = False
    image = {}

    if post.has_file and post.file.file_extension != 'webm' and not (hasattr(post, 'spoiler') and post.spoiler):
        # if there's an image and it's not spoiler, add it
        image = {
            'url': post.file.file_url
        }
        footer = {
            'text': edition
        }
        pushimg = True
    elif post.has_file and post.file.file_extension == 'webm':
        # if it's a webm, add a note about that
        footer = {
            'text': '(A webm is attached) - ' + edition,
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

    # and now we build the data to POST
    data = {
        'embeds': [
            {
                'title': 'No.%d' % post.post_id,
                'description': markdownify(post.comment, post),
                'color': roll_color(post.post_id),
                'timestamp': post.datetime.isoformat(),
                'url': post.url,
                'footer': footer,
                'thumbnail': image
            }
        ]
    }

    # we dump that
    params = json.dumps(data).encode('utf8')

    # and we push to every concerned webhooks
    for hook in dict(config.items(post._thread._board.name)):
        post_discord(params, post._thread._board.name, hook)

    # if this post has an image, push to image-only channels
    if pushimg:
        filepost = {'name': post.file.filename, 'url': post.file.file_url}
        data = {
            'content': '[>>%s](<%s>)' % (post.post_id, post.url)
        }

        for hook in dict(config.items(post._thread._board.name + 'img')):
            post_discord(data, post._thread._board.name + 'img', hook, filepost)


def check_cntumblr():
    # get leaks from sug.rocks
    global cntumblr

    r = requests.get('http://cartoonnetwork.tumblr.com/rss')
    feed = feedparser.parse(r.text)

    for item in feed.entries:
        if not hasattr(item, 'tags'):
            continue
        if item.id not in cntumblr and any('steven universe' in tag.term for tag in item.tags):
            data = {
                'username': feed.feed.title,
                'avatar_url': 'https://sug.rocks/img/CN.jpg',
                'embeds': [
                    {
                        'title': 'New post on Tumblr',
                        'description': markdownify(item.description),
                        'url': item.link,
                        'timestamp': datetime(*item.published_parsed[:-3]).isoformat()
                    }
                ]
            }

            print(crayons.green('Tumblr: ' + item.title))

            params = json.dumps(data).encode('utf8')

            # and we push to every concerned webhooks
            if not firstrun:
                for hook in dict(config.items('news')):
                    post_discord(params, 'news', hook)

            cntumblr.append(item.id)


def check_leaks():
    # get leaks from sug.rocks
    global leaks, firstrun

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


def check_schedule():
    # get schedule from sug.rocks
    global schedule, firstrun

    r = requests.get('https://api.sug.rocks/schedule.json')
    cont = r.json()

    for item in cont:
        # for every leaks
        if item['id'] not in schedule:
            print(crayons.green(item['date'] + ' ' + item['time'] + ': ' + item['title']))
            data = {
                'username': 'Cartoon Network schedule updates',
                'avatar_url': 'https://sug.rocks/img/CN.jpg',
                'embeds': [
                    {
                        'title': item['title'],
                        'description': 'Will air ' + item['date'] + ' at ' + item['time'] + ' EST',
                        'timestamp': datetime.fromtimestamp(item['timestamp']).isoformat(),
                    }
                ]
            }

            params = json.dumps(data).encode('utf8')

            # and we push to every concerned webhooks
            if not firstrun:
                for hook in dict(config.items('schedule')):
                    post_discord(params, 'schedule', hook)

            schedule.append(item['id'])


def check_zap():
    # get schedule from zap2it
    global zap, firstrun

    r = requests.get(config['DEFAULT']['zap'])
    soup = BeautifulSoup(r.text, 'html5lib')
    table = soup.find(id='zc-episode-guide')
    trs = table.find_all('tr')

    for tr in trs[1:6]:  # 5 elements, excluding table header
        # Season number
        s = tr.find(attrs={'itemprop': 'partOfSeason'}).contents[0]
        # Episode number
        e = tr.find(attrs={'itemprop': 'episodeNumber'}).contents[0]
        # Title
        t = tr.find(attrs={'itemprop': 'name'}).contents[0]
        # Air date
        d = tr.find(attrs={'itemprop': 'datePublished'}).contents[0]
        # Paragraph with synopsis
        o = tr.find('p').contents
        if len(o) != 0:  # if there's something inside this <p>, it means we have a synopsis
            p = o[0]
        else:  # if not, well we got nothing
            p = '_None_'

        out = '[S%sE%s] %s (%s) - Airing: %s' % (s, e, t, p, d)

        if out not in zap:  # don't double-post if nothing changes
            print(crayons.green(out))
            data = {
                'username': 'Screener (Zap2It) updates',
                'avatar_url': 'http://tvlistings.zap2it.com/favicon.ico',
                'embeds': [
                    {
                        'title': t,
                        'url': config['DEFAULT']['zap'],
                        'fields': [
                            {
                                'name': 'Air date',
                                'value': d,
                                'inline': True
                            },
                            {
                                'name': 'Episode Number',
                                'value': 'S' + s + 'E' + e,
                                'inline': True
                            },
                            {
                                'name': 'Synopsis',
                                'value': p,
                                'inline': False
                            }
                        ]
                    }
                ]
            }

            params = json.dumps(data).encode('utf8')

            # and we push to every concerned webhooks
            if not firstrun:
                for hook in dict(config.items('zap')):
                    post_discord(params, 'zap', hook)

            zap.append(out)


def check_sug():
    # get data from sug.rocks about current /sug/ threads
    global firstrun

    # fetch our json
    r = requests.get('https://api.sug.rocks/threads.json')
    cont = r.json()

    for item in cont:
        # for every /sug/ thread
        if item['board'] != 'sugen' and not item['status']['archived']:
            # if it's not from /sugen/ and is not archived
            if not any(x['id'] == item['id'] for x in watching):
                # ... and that we don't have it yet
                try:
                    # fetch the thread
                    if item['board'] == 'co':
                        thread = co.get_thread(int(item['id']), False, True)
                    elif item['board'] == 'trash':
                        thread = trash.get_thread(int(item['id']), False, True)

                    # add the thread and some infos to our deque
                    print(crayons.green('\nAdded: ' + item['edition']))
                    watching.append({'id': item['id'], 'edition': item['edition'], 'thread': thread})

                    # if it's not the first run of the script, push to concerned webhooks
                    if not firstrun:
                        push_thread(thread, item['edition'])
                except:
                    pass

    # once done, it's not the first run anymore
    firstrun = False


def check_threads():
    toremove = []
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
                for post in newposts:
                    push_post(post, w['edition'])

    # remove dead threads from the main deque
    for r in toremove:
        watching.remove(r)


if __name__ == '__main__':
    relconf = 0

    while True:
        # always loop
        if relconf > 60:
            # reload our config if needed
            config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini'))
            relconf = 0

        if relconf % 5 == 0:
            check_leaks()
            check_schedule()
            check_zap()
            check_cntumblr()

        check_sug()  # check current /sug/ threads
        check_threads()  # get the threads and new posts
        relconf += 1  # increment that, for reload the config
        sleep(10)  # wait before poking everything again
