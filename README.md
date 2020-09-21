# FIP_mirror

Scripts mirroring the FIP webradios on lastfm, twitter and mastodon.

Since the FIP redesign, the http://www.fipradio.fr/livemeta containing the metadata in xml format isn't available anymore.

You can find the mirrors on the following lastfm accounts :

- [FIPdirect](https://last.fm/user/FIPdirect) for the main channel.
- [FIProck](https://last.fm/user/FIProck) for the rock webradio.
- [FIPreggae](https://last.fm/user/FIPreggae) for the reggae webradio.
- [FIPjazz](https://last.fm/user/FIPjazz) for the jazz webradio.
- [FIPgroove](https://last.fm/user/FIPgroove) for the groove webradio.
- [FIPmonde](https://last.fm/user/FIPmonde) for the musiques du monde webradio.
- [FIPnouveautes](https://last.fm/user/FIPnouveautes) for the nouveautés webradio.
- [FIPelectro](https://last.fm/user/FIPelectro) for the electro webradio.
- [FIPmetal](https://last.fm/user/FIPmetal) for the l'été metal webradio.
- [FIPpop](https://last.fm/user/FIPpop) for the pop webradio.

The following twitter accounts :

- [@fipdirect](https://twitter.com/fipdirect) for the main channel.

The following mastodon accounts :

- [@fipdirect@mamot.fr](https://mamot.fr/@fipdirect) for the main channel.

## Installation

Installation in a virtualenv with pipenv (recommended) :

```
pipenv install '-e .'
```

Classic installation :

```
python setup.py install
```

You will also have to rename/copy the config_sample.ini to config.ini and fill in your credentials.

## Autostarting

A systemd service and its timer are provided in the systemd-service folder. You will have to change the service file to match your configuration.

The timer and the service files allows the script to be run every minute.

```
cp systemd-service/* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now FIP_mirror.timer
```

## Help

```
FIP_mirror -h
```

```
usage: FIP_mirror [-h] [--debug] [--no_headless] [--no_posting]
                         [positional_argument]

Mirror the FIP webradios to several services.

optional arguments:
  -h, --help           show this help message and exit
  --debug              Display debugging information.
  --no_headless        Disable headless mode for the selenium browser.
  --no_posting         Disable posting to lastfm.
```
