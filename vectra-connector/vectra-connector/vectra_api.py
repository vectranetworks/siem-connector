import os
import sys
import time
import backoff
import requests
from datetime import datetime, timedelta
from .logger import logger
from .checkpoint import Checkpoint
from .exception import CustomException, TooManyRequestException
from .push_data_to_syslog import push_data_to_syslog
from .validate_config import read_config

AUTH_URL = f"{str(os.environ.get('BASE_URL')).strip().strip('/')}/oauth2/token"
CLIENT_ID = str(os.environ.get("CLIENT_ID")).strip()
CLIENT_SECRET = str(os.environ.get("CLIENT_SECRET")).strip()


def kill_process_and_exit(e):
    logger.error("Exiting current proccess.")
    sys.exit()


class Auth:
    def __init__(self) -> None:
        """Initialization Function"""

    @backoff.on_exception(
        backoff.expo,
        (
            requests.exceptions.RequestException,
            TooManyRequestException,
            requests.exceptions.HTTPError,
        ),
        max_tries=3,
        on_giveup=kill_process_and_exit,
        max_time=30,
    )
    def auth_token():
        """Generate access token and refresh token for API authentication.

        Returns:
            str: Access Token, Refresh Token
        """
        res = {}

        logger.info("Generating access token.")
        try:
            CLIENT_ID = str(os.environ.get("CLIENT_ID")).strip()
            CLIENT_SECRET = str(os.environ.get("CLIENT_SECRET")).strip()
            res = requests.post(
                AUTH_URL,
                auth=(CLIENT_ID, CLIENT_SECRET),
                data={"grant_type": "client_credentials"},
                timeout=30,
            )
            if res.status_code == 401:
                raise CustomException(f"Status-code {res.status_code} Exception: Client ID or Client Secret is incorrect.")
            if res.status_code == 429:
                raise TooManyRequestException("Too many requests.")
            res.raise_for_status()
            logger.info("Access token is generated.")
            return res.json().get("access_token"), res.json().get('refresh_token')
        except CustomException as e:
            logger.error(f"Error occurred: {e}")
            logger.info("Exiting current execution")
            sys.exit()
        except TooManyRequestException as e:
            logger.info(
                f"{e}. Retrying after {int(res.headers.get('Retry-After'))} seconds."
            )
            time.sleep(int(res.headers.get("Retry-After")))
            raise TooManyRequestException from e
        except requests.exceptions.HTTPError:
            logger.error("Vectra API server is down. Retrying after 10 seconds.")
            time.sleep(10)
            raise requests.exceptions.HTTPError
        except requests.exceptions.RequestException as req_exception:
            logger.error(f"Retrying. An exception occurred: {req_exception}")
            raise requests.exceptions.RequestException from req_exception
        except Exception as e:
            logger.error(f"An exception occurred: {e}")

    @backoff.on_exception(
        backoff.expo,
        (
            requests.exceptions.RequestException,
            TooManyRequestException,
            requests.exceptions.HTTPError,
            CustomException,
        ),
        max_tries=3,
        on_giveup=kill_process_and_exit,
        max_time=30,
    )
    def auth_token_using_refresh_token():
        """Generate access token for API authentication.

        Returns:
            str: Access Token
        """
        res = {}
        global refresh_token
        global access_token
        logger.info("Generating access token using refresh token.")
        try:
            res = requests.post(
                AUTH_URL,
                data={"grant_type": "refresh_token", "refresh_token": f"{refresh_token}"},
                timeout=30,
            )
            if res.status_code == 401:
                raise CustomException("Retrying to generate access token")
            if res.status_code == 429:
                raise TooManyRequestException("Too many requests.")
            res.raise_for_status()
            logger.info("Access token is generated using refresh token.")
            return res.json().get("access_token")
        except CustomException as e:
            logger.error(f"Error occurred: {e}")
            access_token, refresh_token = Auth.auth_token()
            raise CustomException
        except TooManyRequestException as e:
            logger.info(
                f"{e}. Retrying after {int(res.headers.get('Retry-After'))} seconds."
            )
            time.sleep(int(res.headers.get("Retry-After")))
            raise TooManyRequestException from e
        except requests.exceptions.HTTPError:
            logger.error("Vectra API server is down. Retrying after 10 seconds.")
            time.sleep(10)
            raise requests.exceptions.HTTPError
        except requests.exceptions.RequestException as req_exception:
            logger.error(f"Retrying. An exception occurred: {req_exception}")
            raise requests.exceptions.RequestException from req_exception
        except Exception as e:
            logger.error(f"An exception occurred: {e}")


global access_token
global refresh_token
access_token, refresh_token = Auth.auth_token()


class VectraAPI:
    def __init__(self) -> None:
        """Initialization function"""

    @backoff.on_exception(
        backoff.expo,
        (requests.exceptions.HTTPError, requests.exceptions.RequestException),
        max_tries=5,
        on_giveup=kill_process_and_exit,
        max_time=30,
    )
    @backoff.on_exception(
        backoff.expo,
        (CustomException, TooManyRequestException),
        max_tries=3,
        max_time=30,
        on_giveup=kill_process_and_exit,
    )
    def fetch_data_from_api(url, filename, params=None):
        """Collect events from Vectra APIs.

        Args:
            access_token (str): Access token for API authentication
            url (str): URL for event collection

        Returns:
            dict: Events
        """
        global access_token
        global refresh_token
        if params is None:
            params = {}
        params.update({"limit": 1000})

        headers = {"Authorization": f"Bearer {access_token}","User-Agent": "VectraRUX-SIEM-Connect"}
        remaining_count = -1
        conf_data = read_config()
        while remaining_count != 0:
            next_checkpoint = Checkpoint.read_checkpoint_from_file(filename)
            if next_checkpoint == -1:
                current_time = datetime.utcnow()
                # Subtract 24 hours
                new_time = current_time - timedelta(hours=24)
                # Format as "2023-05-31T14:10:00Z"
                formatted_time = new_time.strftime("%Y-%m-%dT%H:%M:%SZ")
                params.update({"event_timestamp_gte": formatted_time})
                next_checkpoint = 0
            params.update({"from": next_checkpoint})
            try:
                logger.info(f"Started Events Collection for '{filename}'.")
                req = requests.get(url, headers=headers, params=params)
                if req.status_code == 401:
                    raise CustomException(
                        f"Status-code {req.status_code} Exception {req.text}"
                    )
                req.raise_for_status()
                total_data = {"events": req.json().get("events")}
                if len(total_data["events"]) < 1:
                    logger.info(f"No new events for '{filename}'.")
                    return
                logger.info(f"Events collected for '{filename}'.")
                Checkpoint.save_checkpoint_to_file(
                    checkpoint={
                        f"{filename}_next_checkpoint": req.json().get(
                            "next_checkpoint"
                        ),
                    },
                    file_name=filename,
                )
                for index in range(len(conf_data.get("configuration").get("server"))):
                    total_data["server"] = index
                    push_data_to_syslog.delay(total_data, index)
                remaining_count = req.json().get("remaining_count")

            except CustomException as e:
                logger.error(f"Error occurred: {e}")
                access_token = Auth.auth_token_using_refresh_token()
                raise CustomException
            except TooManyRequestException as e:
                logger.info(
                    f"{e}. Retrying after {int(req.headers.get('Retry-After'))} seconds."
                )
                time.sleep(int(req.headers.get("Retry-After")))
                raise TooManyRequestException from e
            except requests.exceptions.HTTPError:
                logger.error("Vectra API server is down. Retrying after 10 seconds.")
                time.sleep(10)
                raise requests.exceptions.HTTPError
            except requests.exceptions.RequestException as req_exception:
                logger.error(f"Retrying. An exception occurred: {req_exception}")
                raise requests.exceptions.RequestException from req_exception
            except Exception as e:
                logger.error(f"An exception occurred: {e}")
        return total_data
