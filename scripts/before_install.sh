#!/bin/bash

set -euo pipefail

mkdir -p /home/datamade/bga-payroll

cd /opt/codedeploy-agent/deployment-root/$DEPLOYMENT_GROUP_ID/$DEPLOYMENT_ID/deployment-archive/ && chown -R datamade.datamade .

sudo -H -u datamade blackbox_postdeploy
