import setuptools
import FIP_lastfm_mirror

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="FIP_lastfm_mirror",
    version=FIP_lastfm_mirror.__version__,
    author="dbeley",
    author_email="dbeley@protonmail.com",
    description="Miror the FIP webradios on lastfm.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dbeley/FIP_lastfm_mirror",
    packages=setuptools.find_packages(),
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "FIP_lastfm_mirror=FIP_lastfm_mirror.__main__:main"
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: POSIX :: Linux",
    ],
    install_requires=["pylast", "requests", "bs4", "lxml", "selenium"],
)
