# Packagist version checker
Packagist tracker to check new versions of one or several packages at the same time by a Docker container.

## First steps

### Create a new app or use another you already have created
You can go [here](https://api.slack.com/apps) to create it or check the token of one of your already created apps. This app needs to have the `chat:write` scope at least in order to send the notification.

### Add your slack token and slack channel ID
 This can be modified in the environment variables of the `docker-compose.yml` file

### Modify periodicity time (optional)
The script is made to run every 15 minutes (900 seconds). This can be modified in the entrypoint of the `docker-compose.yml` file

## Create the docker container
In order to create the image and launch the app, just run this command:

```shell
docker compose up -d
```