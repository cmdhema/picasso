# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from aiohttp import web

from aioservice.http import controller
from aioservice.http import requests

from ...common import config
from ...models import app as app_model
from ..views import app as app_view


class AppV1Controller(controller.ServiceController):

    controller_name = "apps"
    version = "v1"

    @requests.api_action(method='GET', route='{project_id}/apps')
    async def list(self, request, **kwargs):
        """
        ---
        description: Listing project-scoped apps
        tags:
        - Apps
        produces:
        - application/json
        responses:
            "200":
                description: Successful operation\
            "401":
                description: Not authorized
        """
        c = config.Config.config_instance()
        log, fnclient = c.logger, c.functions_client
        project_id = request.match_info.get('project_id')
        log.info("[{}] - Listing apps".format(project_id))
        stored_apps = await app_model.Apps.find_by(project_id=project_id)
        final = []
        for app in stored_apps:
            fn_app = await fnclient.apps.show(app.name, loop=c.event_loop)
            final.append(app_view.AppView(app, fn_app).view())
        log.info("[{}] - Apps found: {}".format(project_id, final))
        return web.json_response(
            data={
                self.controller_name: final,
                'message': "Successfully listed applications"
            },
            status=200
        )

    @requests.api_action(method='POST', route='{project_id}/apps')
    async def create(self, request, **kwargs):
        """
        ---
        description: Creating project-scoped app
        tags:
        - Apps
        produces:
        - application/json
        parameters:
        - in: body
          name: app
          description: Created project-scoped app
          required: true
          schema:
            type: object
            properties:
              name:
                type: string
        responses:
            "200":
                description: Successful operation
            "401":
                description: Not authorized
            "409":
                description: App exists
        """
        c = config.Config.config_instance()
        log, fnclient = c.logger, c.functions_client
        project_id = request.match_info.get('project_id')
        data = await request.json()
        log.info("[{}] - Creating app with data '{}'"
                 .format(project_id, str(data)))
        app_name = "{}-{}".format(
            data["app"]["name"],
            project_id)[:30]

        if await app_model.Apps.exists(app_name, project_id):
            log.info("[{}] - Similar app was found, "
                     "aborting".format(project_id))
            return web.json_response(data={
                "error": {
                    "message": "App {0} already exists".format(app_name)
                }
            }, status=409)

        fn_app = await fnclient.apps.create(app_name, loop=c.event_loop)
        log.debug("[{}] - Fn app created".format(project_id))
        stored_app = await app_model.Apps(
            name=app_name, project_id=project_id,
            description=data["app"].get(
                "description",
                "App for project {}".format(
                    project_id))).save()
        log.debug("[{}] - App created".format(project_id))
        return web.json_response(
            data={
                "app": app_view.AppView(stored_app, fn_app).view(),
                "message": "App successfully created",
            }, status=200
        )

    @requests.api_action(method='GET', route='{project_id}/apps/{app}')
    async def get(self, request, **kwargs):
        """
        ---
        description: Pulling project-scoped app
        tags:
        - Apps
        produces:
        - application/json
        responses:
            "200":
                description: Successful operation
            "401":
                description: Not authorized
            "404":
                description: App not found
        """
        c = config.Config.config_instance()
        log, fnclient = c.logger, c.functions_client
        project_id = request.match_info.get('project_id')
        app = request.match_info.get('app')
        log.info("[{}] - Searching for app with name {}"
                 .format(project_id, app))

        if not (await app_model.Apps.exists(app, project_id)):
            log.info("[{}] - App not found, "
                     "aborting".format(project_id))
            return web.json_response(data={
                "error": {
                    "message": "App {0} not found".format(app),
                }
            }, status=404)

        stored_app = (await app_model.Apps.find_by(
            project_id=project_id, name=app)).pop()
        try:
            fn_app = await fnclient.apps.show(app, loop=c.event_loop)
            log.debug("[{}] - Fn app '{}' found".format(project_id, app))
        except Exception as ex:
            log.error("[{}] - Fn app '{}' was not found."
                      "Reason: \n{}".format(project_id, app, str(ex)))
            return web.json_response(data={
                "error": {
                    "message": getattr(ex, "reason", str(ex)),
                }
            }, status=getattr(ex, "status", 500))
        log.debug("[{}] - App '{}' found".format(project_id, app))
        return web.json_response(
            data={
                "app": app_view.AppView(stored_app, fn_app).view(),
                "message": "Successfully loaded app",
            },
            status=200
        )

    @requests.api_action(method='PUT', route='{project_id}/apps/{app}')
    async def update(self, request, **kwargs):
        """
        ---
        description: Updating project-scoped app
        tags:
        - Apps
        produces:
        - application/json
        responses:
            "200":
                description: Successful operation
            "401":
                description: Not authorized
            "404":
                description: App not found
        """
        c = config.Config.config_instance()
        log, fnclient = c.logger, c.functions_client
        project_id = request.match_info.get('project_id')
        app_name = request.match_info.get('app')
        data = await request.json()
        log.info("[{}] - Setting up update procedure "
                 "with data '{}'".format(project_id, data))
        if not (await app_model.Apps.exists(app_name, project_id)):
            log.info("[{}] - App not found, "
                     "aborting".format(project_id))
            return web.json_response(data={
                "error": {
                    "message": "App {0} not found".format(app_name),
                }
            }, status=404)

        try:
            fn_app = await fnclient.apps.update(
                app_name, loop=c.event_loop, **data)
        except Exception as ex:
            log.info("[{}] - Unable to update app, "
                     "aborting. Reason: \n{}".format(project_id, str(ex)))
            return web.json_response(data={
                "error": {
                    "message": getattr(ex, "reason", str(ex)),
                }
            }, status=getattr(ex, "status", 500))

        stored_app = (await app_model.Apps.find_by(
            project_id=project_id, name=app_name)).pop()
        log.info("[{}] - Updating app {} with data {}"
                 .format(project_id, app_name, str(data)))
        return web.json_response(
            data={
                "app": app_view.AppView(stored_app, fn_app).view(),
                "message": "App successfully updated"
            },
            status=200
        )

    @requests.api_action(method='DELETE', route='{project_id}/apps/{app}')
    async def delete(self, request, **kwargs):
        """
        ---
        description: Deleting project-scoped app
        tags:
        - Apps
        produces:
        - application/json
        responses:
            "200":
                description: Successful operation
            "401":
                description: Not authorized
            "404":
                description: App not found
        """
        project_id = request.match_info.get('project_id')
        app = request.match_info.get('app')
        c = config.Config.config_instance()
        log, fnclient = c.logger, c.functions_client
        if not (await app_model.Apps.exists(app, project_id)):
            log.info("[{}] - App not found, "
                     "aborting".format(project_id))
            return web.json_response(data={
                "error": {
                    "message": "App {0} not found".format(app),
                }
            }, status=404)
        try:
            fn_app = await fnclient.apps.show(app, loop=c.event_loop)
            fn_app_routes = await fn_app.routes.list(loop=c.event_loop)
        except Exception as ex:
            log.info("[{}] - Unable to get app, "
                     "aborting. Reason: \n{}".format(project_id, str(ex)))
            return web.json_response(data={
                "error": {
                    "message": getattr(ex, "reason", str(ex)),
                }
            }, status=getattr(ex, "status", 500))

        if fn_app_routes:
            log.info("[{}] - App has routes, unable to delete it, "
                     "aborting".format(project_id))
            return web.json_response(data={
                "error": {
                    "message": ("Unable to delete app {} "
                                "with routes".format(app))
                }
            }, status=403)

        await app_model.Apps.delete(
            project_id=project_id, name=app)
        log.debug("[{}] - App model entry gone".format(project_id))
        await fnclient.apps.delete(app, loop=c.event_loop)
        log.debug("[{}] - Fn app deleted".format(project_id))
        return web.json_response(
            data={
                "message": "App successfully deleted",
            }, status=200)
