"""
This is a modified version of https://github.com/ceph/downburst/blob/master/downburst/iso.py
Which is used to write data to a iso file.
"""

import os
import subprocess
import tempfile
import yaml
import json
from jinja2 import Environment, PackageLoader



class ISO(object):

    def generate_user_yaml(self, user_data, fp):
        fp.write('#cloud-config\n')
        yaml.safe_dump(
            stream=fp,
            data=user_data,
            default_flow_style=False,
            )
        fp.flush()

    def generate_meta_yaml(self, meta_data, fp):
        fp.write('#cloud-config\n')
        yaml.safe_dump(
            stream=fp,
            data=meta_data,
            default_flow_style=False,
            )
        fp.flush()

    def generate_meta_json(self, meta_data, fp):
        json.dump(meta_data,fp)
        fp.flush()



    def generate_meta_iso(
        self,
        name,
        fp,
        meta_data,
        user_data,
        ):
        def gentemp(prefix):
            return tempfile.NamedTemporaryFile(
                prefix='cloudscalers.{prefix}.'.format(prefix=prefix),
                suffix='.tmp',
                )
        with gentemp('meta') as meta_f, gentemp('user') as user_f:
            self.generate_user_yaml(user_data=user_data, fp=user_f)
            self.generate_meta_json(meta_data=meta_data, fp=meta_f)
            subprocess.check_call(
                    args=[
                        'genisoimage',
                        '-quiet',
                        '-input-charset', 'utf-8',
                        '-volid', 'cidata',
                        '-joliet',
                        '-rock',
                        '-graft-points',
                        'user-data={path}'.format(path=user_f.name),
                        'meta-data={path}'.format(path=meta_f.name),
                        ],
                   stdout=fp,
                   close_fds=True,
                   )

    def generate_windows_meta_iso(
        self,
        name,
        fp,
        meta_data,
        user_data,
        ):
        def gentemp(prefix):
            return tempfile.NamedTemporaryFile(
                prefix='cloudscalers.{prefix}.'.format(prefix=prefix),
                suffix='.tmp',
                )
        with gentemp('meta') as meta_f, gentemp('user') as user_f:
            self.generate_user_yaml(user_data=user_data, fp=user_f)
            self.generate_meta_json(meta_data=meta_data, fp=meta_f)
            subprocess.check_call(
                    args=[
                        'genisoimage',
                        '-quiet',
                        '-input-charset', 'utf-8',
                        '-volid', 'config-2',
                        '-joliet',
                        '-rock',
                        '-graft-points',
                        '/openstack/latest/user_data={path}'.format(path=user_f.name),
                        '/openstack/latest/meta_data.json={path}'.format(path=meta_f.name),
                        ],
                   stdout=fp,
                   close_fds=True,
                   )


    def upload_volume(self, vol, length, fp):
        # TODO share with image.upload_volume
        stream = vol.connect().newStream(flags=0)
        vol.upload(stream=stream, offset=0, length=length, flags=0)

        def handler(stream, nbytes, _):
            data = fp.read(nbytes)
            return data
        stream.sendAll(handler, None)
        stream.finish()


    def create_meta_iso(
        self, 
        pool,
        name,
        meta_data,
        user_data,
        type,
        ):
        with tempfile.TemporaryFile() as iso:
            if type not in ['WINDOWS', 'Windows', 'windows']:
                self.generate_meta_iso(
                    name=name,
                    fp=iso,
                    meta_data=meta_data,
                    user_data=user_data,
                   )
            else:
                self.generate_windows_meta_iso(
                    name=name,
                    fp=iso,
                    meta_data=meta_data,
                    user_data=user_data)
            iso.seek(0)
            length = os.fstat(iso.fileno()).st_size
            assert length > 0
            env = Environment(loader=PackageLoader('CloudscalerLibcloud', 'templates'))
            disktemplate = env.get_template("disk.xml")
            diskxml = disktemplate.render({'diskname': 'cloud-init.{name}.iso'.format(name=name), 'disksize': 1})
            vol = pool.createXML(diskxml, flags=0)
            self.upload_volume(
                vol=vol,
                length=length,
                fp=iso,
                )
            return vol
