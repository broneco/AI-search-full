"""Plan/apply existing JHU ACA sidecar rollout. Default invocation is read-only."""
import argparse
import json
from scripts.deployment.jhu_sidecar import AzureClient, DeploymentError, Options, apply_plan, build_plan


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('subscription','azure-tenant','resource-group','app','tenant','sql-host','sql-database',
                 'vault','target-endpoint','revision-suffix'):
        parser.add_argument('--'+name,required=True)
    for name in ('backend-image','helper-image','backend-memory','advanced-model-deployment'):
        parser.add_argument('--'+name)
    parser.add_argument('--backend-cpu',type=float)
    parser.add_argument('--helper-cpu',type=float,default=.25)
    parser.add_argument('--helper-memory',default='0.5Gi')
    parser.add_argument('--verified-model',required=True)
    parser.add_argument('--app-version',required=True)
    parser.add_argument('--expected-fingerprint')
    parser.add_argument('--expected-revision')
    for name in ('apply','migrations-confirmed','resources-confirmed','session-policy-confirmed','models-confirmed','overlap-confirmed'):
        parser.add_argument('--'+name,action='store_true')
    args=parser.parse_args()
    options=Options(**{key:getattr(args,key) for key in Options.__dataclass_fields__})
    try:
        client=AzureClient(options)
        account=client.account()
        # Verify the account before even reading another subscription's app.
        if account.get('id')!=options.subscription or account.get('tenantId')!=options.azure_tenant:
            raise DeploymentError('azure_account_mismatch')
        plan=build_plan(client.read_app(),account,client.secret_metadata(),options)
        if args.apply:
            result=apply_plan(client,plan,options,expected_fingerprint=args.expected_fingerprint,
                expected_revision=args.expected_revision,migrations_confirmed=args.migrations_confirmed,
                resources_confirmed=args.resources_confirmed,session_policy_confirmed=args.session_policy_confirmed,
                models_confirmed=args.models_confirmed,
                overlap_confirmed=args.overlap_confirmed)
        else:result=plan.public
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except DeploymentError as error:
        print(json.dumps({'code':str(error)}));return 1
    except Exception:
        print('{"code":"sidecar_deployment_failed"}');return 1


if __name__=='__main__':raise SystemExit(main())
