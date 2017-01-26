# /sug/ stuff to Discord webhooks
[![PEP8](https://img.shields.io/badge/code%20style-pep8-green.svg)](https://www.python.org/dev/peps/pep-0008/)
[![Gitgud Build Status](https://gitgud.io/sug/sug-discord-webhook/badges/master/build.svg)](https://gitgud.io/sug/sug-discord-webhook/commits/master)
[![Travis Build Status](https://travis-ci.org/sugrocks/sug-discord-webhook.svg?branch=master)](https://travis-ci.org/sugrocks/sug-discord-webhook)

> https://su-g.pw/discord

## Install
```
pip install pipenv # if you don't have it already
pipenv install # will create a virtualenv and get dependencies
cp config.ini.dist config.ini
nano config.ini # follow help at the top of the file to edit it
pipenv run python push-live.py # run in a tmux or something
```

## License
MIT