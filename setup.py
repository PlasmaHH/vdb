from setuptools import setup

setup(
	name="vdb",
	version="1.0",
	license=open("LICENSE", "r").read(),
	long_description=open("README.md", "r").read(),
	author="Dennis Lubert",
	author_email="",
	url="https://github.com/plasmahh/vdb",
	install_requires=[entry for entry in open("requirements.txt", "r").read().split("\n") if len(entry) > 0],
	packages=["vdb"],
	data_files=[('/usr/bin/', ['vdb.py'])],
	scripts=[]
)


# vim: tabstop=4 shiftwidth=4 noexpandtab ft=python
