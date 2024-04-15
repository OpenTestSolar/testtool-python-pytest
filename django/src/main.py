# -*- coding: utf-8 -*-

import argparse
import asyncio
import os
import subprocess
import sys
import shlex
import copy

from solar_testtool import grpcserver, report, servicer, testcase, utils

current_path = os.path.dirname(os.path.abspath(__file__))


default_python_version = utils.check_default_python()
if default_python_version > 2:
    sys.path.append(current_path)
    import djangox
else:
    djangox = None


def shlex_join(split_command):
    """Return a shell-escaped string from *split_command*."""
    return " ".join(shlex.quote(arg) for arg in split_command)


async def create_subprocess(action, proj_path, ipc_fd, testcases=None, envs=None):
    cmdline = """python %s --action=%s --proj-path="%s" --ipc-fd=%d""" % (
        os.path.join(current_path, "djangox.py"),
        action,
        proj_path,
        ipc_fd,
    )

    if testcases:
        cmdline += ' --testcases="%s"' % shlex_join(testcases).replace("$", "\\$")
    utils.logger.info("Run cmdline %s" % cmdline)
    env = None
    if envs:
        env = copy.copy(os.environ)
        env.update(envs)

    if sys.platform != "win32":
        proc = subprocess.Popen(
            cmdline,
            shell=True,
            cwd=proj_path,
            pass_fds=(ipc_fd,),
            env=env,
        )
        await asyncio.sleep(0.5)
        return proc
    else:
        raise NotImplementedError("create_subprocess")


class DjangoUnitTestCommandServicer(servicer.CommandServicerBase):
    async def load_testcases(self, proj_path, test_selectors):
        str_test_selectors = [
            str(it) for it in test_selectors
        ]  # TODO: remove other attributes in test selector

        # django使用import方式加载可能会报错
        testcase_list = []
        r_pipe, w_pipe = utils.create_pipe()
        utils.logger.info(
            "[%s][Load] Pipe %d <=> %d created"
            % (self.__class__.__name__, r_pipe, w_pipe)
        )
        proc = await create_subprocess("collect", proj_path, w_pipe, str_test_selectors)
        os.close(w_pipe)
        pipe = utils.AsyncReadPipe(r_pipe)
        utils.safe_ensure_future(
            pipe.read_message_until_close(lambda it: testcase_list.extend(it))
        )
        while proc and proc.poll() is None:
            await asyncio.sleep(0.1)

        await pipe.wait_for_close()
        utils.logger.info(
            "[%s][Load] Pipe %d <=> %d closed"
            % (self.__class__.__name__, r_pipe, w_pipe)
        )
        testcases = []
        loaderrors = []

        for path, name, attributes in testcase_list:
            if not self.is_testcase_filtered(test_selectors, path, name, attributes):
                if not name and "error" in attributes:
                    loaderrors.append(testcase.LoadError(path, attributes["error"]))
                else:
                    testcases.append(testcase.TestCase(path, name, attributes))
            else:
                utils.logger.info(
                    "[%s] Testcase %s?%s filtered"
                    % (self.__class__.__name__, path, name)
                )
        return testcases, loaderrors

    async def run_testcases(
        self, reporter_url, task_id, context, proj_path, testcases, envs=None
    ):
        # TODO 兼容django的用例
        utils.logger.info(
            "[%s] Run testcases [%s]"
            % (self.__class__.__name__, ", ".join([it.selector for it in testcases]))
        )
        testcase_list = [
            it.file_path[:-2:] + it.name.replace("/", ".") for it in testcases
        ]
        r_pipe, w_pipe = utils.create_pipe()
        utils.logger.info(
            "[%s][Run] Pipe %d <=> %d created"
            % (self.__class__.__name__, r_pipe, w_pipe)
        )

        proc = await create_subprocess(
            "run", proj_path, w_pipe, testcase_list, envs=envs
        )
        os.close(w_pipe)
        await self.create_report_testresults_task(
            r_pipe, reporter_url, task_id, context, testcases
        )
        while proc and proc.poll() is None:
            await asyncio.sleep(0.1)

        utils.logger.info(
            "[%s][Run] Pipe %d <=> %d closed"
            % (self.__class__.__name__, r_pipe, w_pipe)
        )


async def main():
    parser = argparse.ArgumentParser(
        prog="django-unittest-testtool",
        description="Testsolar django-unittest testtool",
    )
    parser.add_argument(
        "--listen", help="grpc server listen address", default="0.0.0.0:8080"
    )
    args = parser.parse_args()

    listen_address = args.listen.split(":")
    server = await grpcserver.start_server(
        DjangoUnitTestCommandServicer(), (listen_address[0], int(listen_address[1]))
    )
    utils.logger.info("Django-Unittest  gRPC server is listening on %s" % args.listen)
    await server.wait_for_termination()


if __name__ == "__main__":
    utils.logger.info("Current default python version is %d" % default_python_version)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
