# Варіант 4

```shell
pyenv install 3.8.6
pyenv local 3.8.6
pipenv shell
pipenv install
waitress-serve --host 127.0.0.1 --port=8080 --call "main:create_app"
```