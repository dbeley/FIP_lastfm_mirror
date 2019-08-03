# FIP_lastfm_mirror

Mirror the FIP webradios on lastfm.

Since the FIP redesign, the http://www.fipradio.fr/livemeta links doesn't seem to be available anymore.

This mirror use webscraping to extract metadata for the webradios. The website is now very javascript-heavy, hence the use of selenium.

You can find the mirrors on the following accounts :

- [FIPdirect](https://last.fm/user/FIPdirect) for the main channel
- [FIProck](https://last.fm/user/FIProck) for the rock webradio
- [FIPreggae](https://last.fm/user/FIPreggae) for the reggae webradio
- [FIPjazz](https://last.fm/user/FIPjazz) for the jazz webradio
- [FIPgroove](https://last.fm/user/FIPgroove) for the groove webradio
- [FIPmonde](https://last.fm/user/FIPmonde) for the monde webradio
- [FIPnouveautes](https://last.fm/user/FIPnouveautes) for the nouveautés webradio
- [FIPelectro](https://last.fm/user/FIPelectro) for the electro webradio
- [FIPmetal](https://last.fm/user/FIPmetal) for the l'été metal webradio


## Installation

Installation in a virtualenv (recommended)

```
pipenv install '-e .'
```

You will also have to rename/copy the config_sample.ini to config.ini and fill in your credentials.

## Autostarting

The script is autostarted with a systemd timers restarting every minutes.

```
cp systemd-service/* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now FIP_lastfm_mirror.timer
```
