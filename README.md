# Vectra : Syslog Connector for Respond UX

## Pre-requisites

Below are the prerequisites for setting up the Vectra SaaS connector.

- Users must have access to a Vectra account with **client\_id** and **client\_secret** for API authentication.
- Users must configure a syslog destination server to receive data over UDP, TCP or TLS.
- **docker (version 24.0.5)**
Refer [https://docs.docker.com/engine/install/#server](https://docs.docker.com/engine/install/#server) for installation instructions. Verify the versions with the commands shown below:

    `$ docker version`

- **docker compose (version 2.20.2)**
Refer [https://docs.docker.com/compose/install/linux/](https://docs.docker.com/compose/install/linux/) for installation instructions. Verify the version with the commands shown below:

    `$ docker compose version`

### Minimum System Requirements

- 4 GB of Memory
- 20 GB of free storage

## Compatibility Matrix

| **Product** | **Product Versions** |
| ----- | ----- |
| Vectra Respond UX (SaaS) API | v3.3 |
| OS | Windows, Linux (Ubuntu) |

## Steps to start connector

Users need to follow following steps to start the connector:

1. Provide following details in docker-compose file:
    - Vectra base URL
   - Vectra client\_id and client\_secret
     ```
      environment:
        BASE_URL: <vectra-base-url>
        CLIENT_ID: <vectra-client-id>
        CLIENT_SECRET: <vectra-client-secret>
     ```

2. Provide destination server details and cron schedules for each APIs in the **config.json** file.
    ```
    {
      "configuration": {
          "server": [
              {
                  "name": "<server-name>",
                  "server_protocol": "<server-protocol>",
                  "server_host": "<destination-server-ip-or-host>",
                  "server_port": <destination-server-port>
              }
          ],
          "scheduler": {
              "audit": "<cron-expression-for-audit>",
              "detections": "<cron-expression-for-detections>",
              "entity_scoring": "<cron-expression-for-entity-scoring>"
          },
          "retry_count": <retry-count>
      }
    }
    ```

    **NOTE**: Replace <> values with actual values.

    Find the ***config.json*** field description [here](#field-description-configjson).

3. In case of TLS servers, provide a TLS configured server **certificate(.pem)** file in the **cert** folder.
    - Certificate file name should be the same as the server name provided in config.json.
4. Place **config.json, cert folder** in the same directory where **docker-compose file** is present.
    ```
    Working directory/
    ├── docker-compose.yml
    ├── config.json
    └── cert/
        └── server1.pem
    ```
5. In case you are using a proxy in your environment
Create a folder to configure the Docker service through systemd:
```
mkdir /etc/systemd/system/docker.service.d
```

Create a service configuration file at /etc/systemd/system/docker.service.d/http-proxy.conf and put the following in the newly created file
```
[Service]
 # NO_PROXY is optional and can be removed if not needed
 # Change proxy_url to your proxy IP or FQDN and proxy_port to your proxy port
 # For Proxy servers that require username and password authentication, just add the proper username and password to the URL. (see example below)

 # Example without authentication
 Environment="HTTP_PROXY=http://proxy_url:proxy_port/" "NO_PROXY=localhost,127.0.0.0/8"

 # Example with authentication
 Environment="HTTP_PROXY=http://username:password@proxy_url:proxy_port/" "NO_PROXY=localhost,127.0.0.0/8"

 # Example for SOCKS5
 Environment="HTTP_PROXY=socks5://proxy_url:proxy_port/" "NO_PROXY=localhost,127.0.0.0/8"
 
```

Reload systemctl to read the new settings:

```
sudo systemctl daemon-reload
```

Verify that the Docker service environment is properly set:

```
sudo systemctl show docker --property Environment
```

Restart the Docker service to use the updated environment settings

```
sudo systemctl restart docker
```

6. Run command **'docker compose up -d'** to start the connector.

## Note

- User need to restart docker compose in case of any update in ***config.json.*** The steps are listed below.
    - Run **'docker compose stop'**
    - Make required changes in ***config.json***
    - Run **'docker compose up -d'** to start the connector.
- A Dockerfile is provided in the ***vectra-connector*** folder but it is not required to build the image locally. A pre-built image has been posted in [Docker Hub](https://hub.docker.com/repository/docker/tmevectra/vectra-saas-siem-connector/general) and is pulled automatically by ***docker-compose***.

## Field description: config.json

| **Field** | **Description** | **Possible Values** |
| :-------: | --------------- | ------------------- |
| **Server Details** |||
| name | Destination server name | alphabets, number, \_ , -(Minimum 1 character) |
| server\_protocol | Protocol supported by destination server | TCP, UDP, TLS, tcp, udp, tls |
| server\_host | Destination server host or IP address | Valid IP or hostname |
| server\_port | Destination server port which is able to receive data on configured protocol | Min: 1Max: 65535 |
| **Scheduler Details** |||
| audit, detections, entity\_scoring | API will fetch events on provided respective cron intervals | Valid cron expression |
| retry\_count | Number of times the connector will retry before exiting in case the server is not reachable(If a negative value is given,the connector will continue retrying until server is reachable) | Positive or negative integer |