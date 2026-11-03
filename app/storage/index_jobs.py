"""Tenant-scoped durable status and compare-and-swap leases; never stores model inputs."""
from datetime import timedelta
import uuid

from sqlalchemy import func, inspect, select, update
from sqlalchemy.exc import IntegrityError

from app.core.model_config import ModelError
from app.storage.models import DBIndexPreparationJob as Job
from app.storage.vector_store import tenant_key
from app.retrieval.filters import exact_value

ACTIVE = {"queued", "running", "cancelling"}
LEASE_SECONDS = 90


def available(db) -> bool:
    return inspect(db.connection()).has_table(Job.__tablename__)


def require_schema(db):
    if not available(db):
        raise ModelError("index_jobs_migration_required", "Nejdříve proveďte migraci správy indexů.", 503)


def now(db):
    return db.scalar(select(func.current_timestamp()))


def current(db, tenant):
    row = db.get(Job, tenant_key(tenant), populate_existing=True)
    if row is not None and row.tenant_id != tenant:
        raise ModelError("index_job_tenant_mismatch", "Úloha nepatří tomuto tenantu.", 403)
    return row


def public(db, row):
    if row is None:
        return None
    state = "interrupted" if row.state in ACTIVE and row.lease_until <= now(db) else row.state
    logical_id = row.index_id
    if row.index_id is not None:
        from app.storage.models import DBSearchIndex
        from app.storage.index_settings import metadata
        index = db.get(DBSearchIndex, row.index_id)
        spec = metadata(db, index) if index is not None and index.tenant_id == row.tenant_id else None
        logical_id = spec.owner_index_id if spec is not None and spec.owner_index_id else row.index_id
    return dict(job_id=str(row.job_id), index_id=str(row.index_id) if row.index_id else None,
                logical_index_id=str(logical_id) if logical_id else None,
                embedding_profile=row.embedding_profile, action=row.action, state=state,
                processed_chunks=row.processed_chunks, valid_chunks=row.valid_chunks,
                total_chunks=row.total_chunks, error_code=row.error_code,
                activity=row.activity,
                created_at=row.created_at.isoformat()+"Z", updated_at=row.updated_at.isoformat()+"Z")


def begin(db, principal, entry, action, index_id):
    """Exactly one active tenant operation, including competing HTTP workers/replicas."""
    require_schema(db)
    row = current(db, principal.tenant_id)
    stamp = now(db)
    if row is not None and row.state in ACTIVE and row.lease_until > stamp:
        if (row.embedding_profile == entry.id and row.action == action and (index_id is None or row.index_id == index_id)
                and row.state != "cancelling"):
            return row, False
        raise ModelError("index_preparation_busy", "Jiná úloha indexu právě běží.", 409)
    values = dict(tenant_id=principal.tenant_id, job_id=uuid.uuid4(), index_id=index_id,
                  requested_by=principal.user_id, embedding_profile=entry.id, profile_id=entry.space().profile_id,
                  action=action, state="queued", processed_chunks=0, valid_chunks=0, total_chunks=0,
                  error_code=None, activity=None, created_at=stamp, updated_at=stamp,
                  lease_until=stamp+timedelta(seconds=LEASE_SECONDS))
    try:
        if row is None:
            row = Job(tenant_key=tenant_key(principal.tenant_id), revision=1, **values)
            db.add(row)
        else:
            result = db.execute(update(Job).where(Job.tenant_key == row.tenant_key, Job.revision == row.revision)
                                .values(**values, revision=row.revision+1).execution_options(synchronize_session=False))
            if result.rowcount != 1:
                db.rollback()
                raise ModelError("index_preparation_busy", "Stav úlohy se změnil. Obnovte přehled.", 409)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ModelError("index_preparation_busy", "Jiná úloha byla spuštěna současně. Obnovte přehled.", 409) from None
    return current(db, principal.tenant_id), True


def owned(db, tenant, job_id, *, allow_cancel=False):
    row = db.scalar(select(Job).where(Job.tenant_key == tenant_key(tenant))
        .with_hint(Job, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql")
        .execution_options(populate_existing=True))
    if row is not None and row.tenant_id != tenant:
        raise ModelError("index_job_tenant_mismatch", "Úloha nepatří tomuto tenantu.", 403)
    if row is None or row.job_id != job_id or row.state not in ACTIVE or row.lease_until <= now(db):
        raise ModelError("index_job_lease_lost", "Úloha byla přerušena; hotové dávky jsou zachované.", 409)
    if row.state == "cancelling" and not allow_cancel:
        raise ModelError("index_job_cancelled", "Úloha byla zastavena.", 409)
    return row


def touch(db, tenant, job_id, **patch):
    stamp = now(db)
    result = db.execute(update(Job).where(Job.tenant_key == tenant_key(tenant), exact_value(Job.tenant_id, tenant, db.bind.dialect.name),
        Job.job_id == job_id, Job.state.in_(ACTIVE), Job.lease_until > stamp)
        .values(**patch, updated_at=stamp, lease_until=stamp+timedelta(seconds=LEASE_SECONDS),
                revision=Job.revision+1).execution_options(synchronize_session=False))
    db.commit()
    if result.rowcount != 1:
        raise ModelError("index_job_lease_lost", "Platnost úlohy vypršela. Obnovte přehled.", 409)


def claim(db, tenant, job_id):
    stamp = now(db)
    result = db.execute(update(Job).where(Job.tenant_key == tenant_key(tenant),
        exact_value(Job.tenant_id, tenant, db.bind.dialect.name), Job.job_id == job_id,
        Job.state == "queued", Job.lease_until > stamp)
        .values(state="running", revision=Job.revision+1).execution_options(synchronize_session=False))
    db.commit()
    return result.rowcount == 1


def cancel(db, tenant, job_id):
    row = current(db, tenant)
    if row is None or row.job_id != job_id:
        raise ModelError("index_job_not_found", "Úloha nebyla nalezena.", 404)
    if row.state in ACTIVE and row.lease_until > now(db):
        touch(db, tenant, job_id, state="cancelling")
    return public(db, current(db, tenant))
