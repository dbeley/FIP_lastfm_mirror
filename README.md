# FIP_lastfm_mirror

Mirror the FIP webradios on lastfm.

Since the FIP redesign, the http://www.fipradio.fr/livemeta links doesn't seem to be available anymore.

This mirror use webscraping to extract metadata for the webradios. The website is now very javascript-heavy, hence the use of selenium.

You can find the deployed mirrors on the following accounts :

	- fipdirect for the main channel


## Installation

Installation in a virtualenv (recommended)

```
pipenv install '-e .'
```

