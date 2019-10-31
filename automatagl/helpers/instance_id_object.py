import requests

class InstanceIDObject:
    """
    A instance object to try and get the instance id from metadata
    """

    def __init__(self) -> None:
        self.instance_id = None

    def check_ec2_instance(self):
        if self.instance_id is None:
            try:
                metadata = requests.get("http://169.254.169.254/latest/dynamic/instance-identity/document", timeout=2)
                response_json = metadata.json()
                self.instance_id = response_json.get('instanceId')
            except:
                 pass
        return self.instance_id

    def check_gcp_instance(self):
        if self.instance_id is None:
            try:
                metadata_server = "http://metadata/computeMetadata/v1/instance/"
                metadata_header = {'Metadata-Flavor' : 'Google'}
                self.instance_id = requests.get(metadata_server + 'id', headers = metadata_header, timeout=2).text
            except:
                pass
        return self.instance_id

    def find_instance_id(self):
       self.check_ec2_instance()
       self.check_gcp_instance()
       return self.instance_id