import os
import sys
import json
import crayons
import configparser
import urllib.error
import urllib.parse
import urllib.request
from time import sleep
import basc_py4chan as fch
from collections import deque
from datetime import datetime

# count stuff
relconf = 0
firstrun = True

# init config and list of watched threads
config = configparser.ConfigParser()
watching = deque('')

# init 4chan boards
co = fch.Board('co', True)
trash = fch.Board('trash', True)


def roll_color(id):
    last = int(str(id)[-1:])
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


def post_discord(params, cat, hook):
    # post to Discord
    # set content to json and use a 'normal' UA
    headers = {
        'content-type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (compatible; sug/1.0)'
    }
    # build our webhook url
    url = "https://discordapp.com/api/webhooks/%s/%s" % (hook, config.get(cat, hook))
    # and build the request
    req = urllib.request.Request(url, data=params, headers=headers)

    try:
        # make the request
        response = urllib.request.urlopen(req)
    except:
        # try one more time
        try:
            print(crayons.yellow('\nPOSTing to Discord failed, will retry...'))
            sleep(3)
            response = urllib.request.urlopen(req)
        except:
            # give up
            print(crayons.red('\nPOSTing to Discord failed again...'))
            return

    # get content
    rep = response.read().decode('utf8')
    if rep != '':
        # if we have something in return, it's not good
        print(crayons.red('\n' + rep))


def push_thread(thread, edition=''):
    # if no edition found, just return "/sug/" and the thread number
    if edition == '':
        edition = '/sug/ no.' + thread.topic.post_id

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
        'username': 'New Thread',
        'embeds': [
            {
                'title': '[/' + thread._board.name + '/] ' + edition,
                'color': roll_color(post.post_id),
                'url': thread.url,
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
        data = {
            'username': post.name,
            'content': '[>>%s](%s)' % (post.post_id, post.url),
            'embeds': [
                {
                    'color': roll_color(post.post_id),
                    'image': {
                        'url': post.file.file_url
                    },
                    'footer': {
                        'text': '[/' + post._thread._board.name + '/] ' + edition
                    }
                }
            ]
        }
        params = json.dumps(data).encode('utf8')

        for hook in dict(config.items(thread._board.name + 'img')):
            post_discord(params, thread._board.name + 'img', hook)


def push_post(post, edition=''):
    # default
    pushimg = False
    image = {}
    footer = {}

    if post.has_file and post.file.file_extension != 'webm' and not (hasattr(post, 'spoiler') and post.spoiler):
        # if there's an image and it's not spoiler, add it
        image = {
            'url': post.file.file_url
        }
        footer = {
            'text': '[/' + post._thread._board.name + '/] ' + edition
        }
        pushimg = True
    elif post.has_file and post.file.file_extension == 'webm':
        # if it's a webm, add a note about that
        footer = {
            'text': '(A webm is attached) - [/' + post._thread._board.name + '/] ' + edition,
            'icon_url': 'https://s.kdy.ch/4ch-warning.png'
        }
    elif hasattr(post, 'spoiler') and post.spoiler:
        # if it was spoiled, add a note about that
        footer = {
            'text': '(Image is spoiled) - [/' + post._thread._board.name + '/]' + edition,
            'icon_url': 'https://s.kdy.ch/4ch-warning.png'
        }
    else:
        footer = {
            'text': '[/' + post._thread._board.name + '/] ' + edition
        }

    # and now we build the data to POST
    data = {
        'username': post.name,
        'embeds': [
            {
                'title': 'No.%d' % post.post_id,
                'description': post.text_comment,
                'color': roll_color(post.post_id),
                'url': post.url,
                'footer': footer,
                'image': image
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
        data = {
            'username': post.name,
            'content': '[>>%s](%s)' % (post.post_id, post.url),
            'embeds': [
                {
                    'color': roll_color(post.post_id),
                    'image': {
                        'url': post.file.file_url
                    },
                    'footer': {
                        'text': '[/' + post._thread._board.name + '/] ' + edition
                    }
                }
            ]
        }
        params = json.dumps(data).encode('utf8')

        for hook in dict(config.items(post._thread._board.name + 'img')):
            post_discord(params, post._thread._board.name + 'img', hook)


def check_config():
    # reload config after 60 runs
    global relconf

    if relconf > 60:
        relconf = 0
    if relconf == 0:
        config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini'))


def check_sug():
    # get data from sug.rocks about current /sug/ threads
    global relconf, firstrun

    # fetch our json
    req = urllib.request.Request('https://api.sug.rocks/threads.json')
    r = urllib.request.urlopen(req).read()
    cont = json.loads(r.decode('utf-8'))

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
                sys.stdout.write('\r[{0}] {1}'.format(
                    crayons.blue(str(datetime.now())),
                    crayons.green(str(w['id']) + ': ' + str(upcount) + ' new posts')))
                newposts = w['thread'].all_posts[-upcount:]
                for post in newposts:
                    push_post(post, w['edition'])

    # remove dead threads from the main deque
    for r in toremove:
        watching.remove(r)


if __name__ == '__main__':
    while True:
        # always loop
        check_config()  # load our config if needed
        check_sug()  # check current /sug/ threads
        check_threads()  # get the threads and new posts
        relconf += 1  # increment that, for reload the config
        sleep(10)  # wait before poking everything again
