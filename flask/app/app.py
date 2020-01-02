# Copyright (C) 2019 Kristian Sloth Lauszus.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
# Contact information
# -------------------
# Kristian Sloth Lauszus
# Web      :  http://www.lauszus.com
# e-mail   :  lauszus@gmail.com

import functools
import hashlib
import os
import re
import threading
from typing import Optional, Tuple

import requests
from flask import abort, request, Response, send_from_directory, make_response
from github import Github, GitRelease, Repository, UnknownObjectException
from packaging.version import parse
from werkzeug.http import http_date

from . import app, scheduler

_release_lock = threading.RLock()


def md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def md5sums(dirname: str, file_names: Optional[list] = None) -> bool:
    # Flag to make sure that at least one file parses the checksum verification
    check_verified = False
    file_names_not_verified = file_names.copy() if file_names is not None else None

    # Verify MD5SUMS, if present
    try:
        with open(os.path.join(dirname, 'MD5SUMS'), 'rt') as f:
            for line in f:
                cksum, fname = re.split(r'\s+', line.strip(), maxsplit=1)
                if file_names is not None and fname not in file_names:
                    app.logger.info('Skipping checksum of "{}"'.format(fname))
                    continue
                file_path = os.path.join(dirname, fname)
                app.logger.debug('Verifying checksum of "{}"'.format(file_path))
                if cksum != md5(file_path):
                    app.logger.error('Checksum failed for: "{}"'.format(file_path))
                    return False
                else:
                    app.logger.info('Checksum verified for: "{}"'.format(file_path))
                    if file_names_not_verified is not None:
                        # Remove the file we just verified
                        file_names_not_verified.remove(fname)
                    check_verified = True
    except (IOError, OSError, ValueError):
        app.logger.exception('Failed to read MD5SUMS file')
        return False

    if file_names_not_verified is not None and len(file_names_not_verified) > 0:
        app.logger.error('Not all files were present in the download: {}'.format(file_names_not_verified))
        return False

    if check_verified is False:
        app.logger.error('No files parsed the checksum verification')

    return check_verified


def nocache(view):
    @functools.wraps(view)
    def no_cache(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers['Last-Modified'] = http_date()
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response

    return functools.update_wrapper(no_cache, view)


def _get_latest_downloaded_release() -> Optional[str]:
    with _release_lock:
        # Sort the subdirectories using 'parse', as all the subdirectories will be named after the tags
        try:
            dirnames = next(os.walk(os.path.join(app.config['UPDATE_FOLDER'], 'PlantFriends')))[1]
        except StopIteration:
            app.logger.warning('No release was downloaded')
            return None

    # Return the latest tag
    latest_tag = sorted(dirnames, key=parse)[-1]
    app.logger.info('Latest release: {}'.format(latest_tag))
    return latest_tag


@app.route('/update', methods=['GET'])
@nocache
def update():
    # See: https://arduino-esp8266.readthedocs.io/en/latest/ota_updates/readme.html
    if request.headers.get('User-Agent') != 'ESP8266-http-Update':
        app.logger.warning('Invalid User-Agent header: {}'.format(request.headers.get('User-Agent')))
        abort(403)

    for header in ['x-ESP8266-Chip-ID', 'x-ESP8266-STA-MAC', 'x-ESP8266-AP-MAC', 'x-ESP8266-free-space',
                   'x-ESP8266-sketch-size', 'x-ESP8266-sketch-md5', 'x-ESP8266-chip-size', 'x-ESP8266-sdk-version']:
        if header not in request.headers:
            app.logger.warning('Missing ESP header: {} in {}'.format(header, request.headers))
            abort(403)

    if not request.headers.get('x-ESP8266-version'):
        app.logger.warning('Missing current version: {}'.format(request.headers.get('x-ESP8266-version')))
        abort(403)

    if not request.headers.get('x-ESP8266-mode'):
        app.logger.warning('Missing mode: {}'.format(request.headers.get('x-ESP8266-mode')))
        abort(403)

    current_version = request.headers.get('x-ESP8266-version')
    spiffs = request.headers.get('x-ESP8266-mode') == 'spiffs'

    # We need to make sure that no new files are created while we check for the latest release
    with _release_lock:
        latest_release = _get_latest_downloaded_release()
        if latest_release is None:
            app.logger.warning('No local release was found')
            return Response(status=304, mimetype='text/plain')

        # Check if the latest tag is newer than the current version
        if parse(latest_release) <= parse(current_version):
            app.logger.info('"{}" is already the newest version'.format(current_version))
            return Response(status=304, mimetype='text/plain')

        # Get the requested binary from the latest release folder
        dirname = os.path.join(app.config['UPDATE_FOLDER'], 'PlantFriends', latest_release)
        filename = 'PlantFriends_spiffs.bin' if spiffs else 'PlantFriends_firmware.bin'
        if md5sums(dirname, [filename]) is False:
            app.logger.error('Checksum failed for "{}{}{}"'.format(dirname, os.path.sep, filename))
            return Response(status=304, mimetype='text/plain')

        # Send the file including the MD5 checksum
        response = make_response(send_from_directory(dirname, filename, as_attachment=True,
                                                     mimetype='application/octet-stream'))
        response.headers['x-MD5'] = md5(os.path.join(dirname, filename))
        return response


def download_latest_release(owner: str, repo_name: str, current_version: str, file_names: Optional[list] = None) \
        -> Optional[Tuple[str, str, str]]:
    try:
        g = Github()
        repo = g.get_repo(owner + '/' + repo_name)  # type: Repository
        try:
            if list(repo.get_releases()):
                release = repo.get_latest_release()  # type: GitRelease
                if parse(release.tag_name) <= parse(current_version):
                    app.logger.info('"{}" is already the newest version: {}'.format(repo.full_name, current_version))
                    return None
            else:
                app.logger.warning('No release was available for "{}"'.format(repo.full_name))
                return None
        except UnknownObjectException:
            # This is triggered when a tag has been created, but no Github release has been made yet
            app.logger.exception('Error getting release for "{}"'.format(repo.full_name))
            return None

        # We need to make sure that it does not try to read the folder until we are done downloading the files
        with _release_lock:
            dirname = os.path.join(app.config['UPDATE_FOLDER'], repo.name, release.tag_name)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            elif md5sums(dirname, file_names) is True:
                app.logger.info('"{}" was already downloaded'.format(dirname))
                return dirname, release.tag_name, release.body

            for a in release.get_assets():
                if file_names is not None and a.name not in file_names + ['MD5SUMS']:
                    app.logger.info('Skipping "{}"'.format(a.name))
                    continue

                # Download the file using the Github API
                url = 'https://api.github.com/repos/{}/{}/releases/assets/{}'.format(owner, repo_name, a.id)
                app.logger.info('Downloading "{}" from {}'.format(a.name, url))

                response = requests.get(url, allow_redirects=True, headers={'Accept': 'application/octet-stream'},
                                        stream=True)
                if response.status_code != 200:
                    app.logger.error('Failed to download "{}", status code: {}'.format(a.name, response.status_code))
                    return None
                with open(os.path.join(dirname, a.name), 'wb') as f:
                    f.write(response.content)

            return (dirname, release.tag_name, release.body) if md5sums(dirname, file_names) is True \
                else None
    except requests.exceptions.ConnectionError:
        return None


@scheduler.scheduled_job('interval', hours=24)
def check_github_release():
    try:
        owner, repo_name, version = 'MadsBornebusch', 'PlantFriends', _get_latest_downloaded_release() or '0'
        result = download_latest_release(owner, repo_name, version)
        if result is not None:
            dirname, version, body = result
            app.logger.info('{}-{} was successfully downloaded to "{}", body: {}'.format(repo_name, version, dirname,
                                                                                         repr(body)))
    except Exception as e:
        # Catch and log the exception, so an email is sent
        app.logger.exception('Failed to get latest Github release')
        raise e