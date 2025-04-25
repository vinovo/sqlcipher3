sqlcipher3
==========
(forked from https://github.com/coleifer/sqlcipher3)

To install, run 
```
pip install .
```


## Distributing
Run:
```
python setup.py sdist
twine upload dist/*
```

**Important!!**
* Make sure you don't have any already compiled / built files under dependencies/sqlcipher, if they get packaged into the distribution, the build on some system will fail!
* To clean them up, do the following
```
cd dependencies/sqlcipher
git add .
git stash
```


## What has changed compared to original?
Static library are linked via `sqlite3.c` and `sqlite3.h`. These 2 files are obtained by running
```
git clone https://github.com/sqlcipher/sqlcipher
cd sqlcipher/
./configure
make sqlite3.c
```

Other changes, see https://github.com/coleifer/sqlcipher3/pull/28/files