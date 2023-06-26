# razdor.chat API
The readme is being worked on.

Documentation @ http://razdor.chat/docs/swagger

Examples @ https://github.com/RazdorChat/examples

# Dependencies
## Python
3.10+
### Pip
* sanic[ext]==23.3.0
* jsonschema==4.17.3
* redis==4.5.5 mariadb==1.1.6
* argon2-cffi

## MariaDB
10.11.3
* https://downloads.mariadb.org/mariadb/10.11.3/
### Schema
* https://github.com/RazdorChat/sql

## Redis
6.0.16+
* https://github.com/redis/redis

# Help
Feel free to fork and add some changes, then do a pr.
Discord link (ironic, i know) is on the official website: https://razdor.chat

All config data left over from testing should be changed, along with the access key.

# Selfhosting
## DB
* Only providing support for MariaDB (10.11) \
Schema files are in [here](https://github.com/RazdorChat/sql)

* Fill out all JSON files in `server_data`
