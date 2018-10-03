#  Copyright (c) 2018 Sony Pictures Imageworks Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.


"""Cue3 integration module."""

import versions
import sys
import logging
import time
import os

from xml.etree import ElementTree as Et
from xml.dom.minidom import parseString

from outline import config, util, OutlineException
from outline.depend import DependType
from outline.manifest import FileSequence

import Cue3

logger = logging.getLogger("outline.backend.cue3")

__all__ = ["launch",
           "serialize"]

def build_command(launcher, layer):
    """
    Build and return a pycurun shell command for the given layer

    @type  launcher : OutlineLauncher
    @param launcher : The outline launcher.

    @type  layer : Layer
    @param layer : The layer to build a command for.

    @rtype: list
    @return: The shell command to run for a the given layer.
        """
    command = []

    if layer.get_arg("strace"):
        command.append("strace")
        command.append("-ttt")
        command.append("-T")
        command.append("-e")
        command.append("open,stat")
        command.append("-f")
        command.append("-o")
        command.append("%s/strace.log" % layer.get_path())

    if layer.get_arg("wrapper"):
        wrapper = layer.get_arg("wrapper")
    elif layer.get_arg("setshot", True):
        wrapper = "%s/cue3_wrap_frame" % config.get("outline","wrapper_dir")
    else:
        wrapper = "%s/cue3_wrap_frame_no_ss" % config.get("outline","wrapper_dir")

    command.append(wrapper)
    command.append(config.get("outline", "user_dir"))
    command.append("%s/pycuerun" % config.get("outline", "bin_dir"))
    command.append("%s -e #IFRAME#-%s" % (launcher.get_outline().get_path(),
                                          layer.get_name()))
    command.append(" --version %s" % versions.get_version("outline"))
    command.append(" --repos %s" % versions.get_repos())
    command.append("--debug")

    if launcher.get("dev"):
        command.append("--dev")

    if launcher.get("devuser"):
        command.append("--dev-user %s" % launcher.get("devuser"))

    return command

def launch(launcher):
    """
    Launch the given L{OutlineLauncher}.

    @type launcher: L{OutlineLauncher}
    @param launcher: The OutlineLauncher to launch.

    @rtype: Cue3.Entity.Job
    @return: The Cue3 job that was launched.
    """

    # Disable the network timeout for Cue3.
    Cue3.Cuebot.setTimeout(0)

    if launcher.get("server"):
        Cue3.Cuebot.setHosts([launcher.get("server")])
        logger.info("cue3bot host set to: %s" % launcher.get("server"))

    job = Cue3.Cuebot.Proxy.launchSpecAndWait(launcher.serialize())[0]

    if launcher.get("wait"):
        wait(job)
    elif launcher.get("test"):
        test(job)

    return job

def test(job):
    """
    Test the given job.  This function returns immediatly
    when the given job completes, or throws an L{OutlineException}
    if the job fails in any way.

    @type job: Cue3.Entity.Job
    @param job: The job to test.
    """
    logging.basicConfig(level=logging.DEBUG)
    logger.info("Entering test mode for job: %s" % job.data.name)

    # Unpause the job.
    job.proxy.resume()

    try:
        while True:
            try:
                job = Cue3.getJob(job)
                if job.stats.deadFrames + job.stats.eatenFrames > 0:
                    msg = "Job test failed, dead or eaten frames on: %s"
                    raise OutlineException(msg % job.data.name)
                if job.data.state == Cue3.JobState.Finished:
                    break
                msg = "waiting on %s job to complete: %d/%d"
                logger.debug(msg % (job.data.name, job.stats.succeededFrames,
                                   job.stats.totalFrames))
            except Cue3.CueIceException, ie:
                raise OutlineException("test for job %s failed: %s" %
                                       (job.data.name, ie))
            time.sleep(5)
    finally:
        job.proxy.kill()

def wait(job):
    """
    Wait for the given job to complete before returning.

    @type job: Cue3.Entity.Job
    @param job: The job to wait on.
    """
    while True:
        try:
            if not Cue3.isJobPending(job.data.name):
                break
            msg = "waiting on %s job to complete: %d/%d"
            logger.debug(msg % (job.data.name, job.stats.succeededFrames,
                               job.stats.totalFrames))
        except Cue3.CueIceException, ie:
            msg = "Cue3 error waiting on job: %s, %s. Will continue to wait."
            print >> sys.stderr, msg % (job.data.name, ie)
        except Exception, e:
            msg = "Cue3 error waiting on job: %s, %s. Will continue to wait."
            print >> sys.stderr, msg % (job.data.name, e)
        time.sleep(5)

def serialize(launcher):
    """
    Serialize the outline part of the given L{OutlineLauncher} into a
    Cue3 job specification.

    @type launcher: L{OutlineLauncher}
    @param launcher: The outline launcher being used to launch the job.

    @rtype: str
    @return: A Cue3 job specification.
    """
    ol = launcher.get_outline()

    root = Et.Element("spec")
    depends = Et.Element("depends")

    subElement(root, "facility", launcher.get("facility"))
    subElement(root, "show", util.get_show())
    subElement(root, "shot", launcher.get("shot"))
    user = launcher.get_flag("user")
    if not user:
        user = util.get_user()
    subElement(root, "user", user)
    if not launcher.get("nomail"):
        subElement(root, "email", "%s@%s" % (util.get_user(),
                                             config.get("outline", "domain")))
    subElement(root, "uid", str(util.get_uid()))

    j = Et.SubElement(root, "job", {"name": ol.get_name()})
    subElement(j, "paused", str(launcher.get("pause")))
    subElement(j, "maxretries", str(launcher.get("maxretries")))
    subElement(j, "autoeat", str(launcher.get("autoeat")))

    if ol.get_arg("localbook"):
        Et.SubElement(j, "localbook", ol.get_arg("localbook"))

    if launcher.get("os"):
        subElement(j, "os", launcher.get("os"))
    elif os.environ.get("OL_OS", False):
        subElement(j, "os", os.environ.get("OL_OS"))

    env = Et.SubElement(j, "env")
    for env_k, env_v in ol.get_env().iteritems():
        # Only pre-setshot environement variables are
        # passed up to the cue.
        if env_v[1]:
            pair = Et.SubElement(env, "key", {"name": env_k})
            pair.text = env_v[0]

    layers = Et.SubElement(j, "layers")
    for layer in ol.get_layers():

        # Unregisterd layers are in the job, but, don't show up on the cue.
        if not layer.get_arg("register"):
            continue

        # Don't register child layers with Cue3.
        if layer.get_parent():
            continue

        # The layer will return a valid range if its range and
        # the job's range are compatible.  If not, skip launching
        # that layer.
        range = layer.get_frame_range();
        if not range:
            logger.info("Skipping layer %s, its range (%s) does not intersect "
                        "with ol range %s" % (layer, layer.get_arg("range"),
                                              ol.get_frame_range()))
            continue

        spec_layer = Et.SubElement(layers, "layer",
                                   {"name": layer.get_name(),
                                    "type": layer.get_type() })
        subElement(spec_layer, "cmd",
                   " ".join(build_command(launcher, layer)))
        subElement(spec_layer, "range", str(range))
        subElement(spec_layer, "chunk", str(layer.get_chunk_size()))

        # Cue3 specific options
        if layer.get_arg("threads"):
            subElement(spec_layer, "cores", "%0.1f" % (layer.get_arg("threads")))

        if layer.is_arg_set("threadable"):
            subElement(spec_layer, "threadable",
                       bool_to_str(layer.get_arg("threadable")))

        if layer.get_arg("memory"):
            subElement(spec_layer, "memory", "%s" % (layer.get_arg("memory")))

        if os.environ.get("OL_TAG_OVERRIDE", False):
            subElement(spec_layer, "tags",
                       scrub_tags(os.environ["OL_TAG_OVERRIDE"]))
        elif layer.get_arg("tags"):
            subElement(spec_layer, "tags", scrub_tags(layer.get_arg("tags")))

        services = Et.SubElement(spec_layer, "services")
        service = Et.SubElement(services, "service")
        try:
            service.text = layer.get_service().split(",")[0].strip()
        except Exception, e:
            service.text = "default"

        buildDependencies(ol, layer, depends)

    if not len(layers):
        raise OutlineException("Failed to launch job.  There are no layers with frame "
                               "ranges that intersect the job's frame range: %s"
                               % ol.get_frame_range())

    # Dependencies go after all of the layers
    root.append(depends)

    xml = []
    xml.append('<?xml version="1.0"?>')
    xml.append('<!DOCTYPE spec PUBLIC "SPI Cue  Specification Language" "http://localhost:8080/spcue/dtd/cjsl-1.8.dtd">')
    xml.append(Et.tostring(root))

    result = "".join(xml)
    logger.debug(parseString(result).toprettyxml())
    return result

def scrub_tags(tags):
    """
    Ensure that layer tags pass in as a string are formatted properly.
    """
    if isinstance(tags, (basestring,)):
        tags = [tag.strip() for tag in tags.split("|")
                if tag.strip().isalnum()]
    return " | ".join(tags)

def bool_to_str(value):
    """
    If the given value evaluates to True, return
    "True", else return "False"
    """
    if value:
        return "True"
    return "False"

def buildDependencies(ol, layer, all_depends):
    """
    Iterate through all the layer's dependencies and
    add them to the job spec.
    """
    for dep in layer.get_depends():

        depend = Et.SubElement(all_depends, "depend",
                               type=dep.get_type(),
                               anyframe= str(dep.is_any_frame()))

        if dep.get_type() == DependType.LayerOnSimFrame:

            frame_range = dep.get_depend_on_layer().get_frame_range()
            first_frame = FileSequence.FrameSet(frame_range)[0]

            subElement(depend, "depjob", ol.get_name())
            subElement(depend, "deplayer", layer.get_name())
            subElement(depend, "onjob", ol.get_name())
            subElement(depend, "onframe", "%04d-%s"
                       % (first_frame, dep.get_depend_on_layer().get_name()))
        else:
            subElement(depend, "depjob", ol.get_name())
            subElement(depend, "deplayer", layer.get_name())
            subElement(depend, "onjob", ol.get_name())
            subElement(depend, "onlayer", dep.get_depend_on_layer().get_name())

def subElement(root, tag, text):
    """Convinience method to create a sub element with text"""
    e = Et.SubElement(root, tag)
    e.text = text
    return e
