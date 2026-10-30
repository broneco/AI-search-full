"""SQL Server join hints scoped to a single relational join, never nested filters."""
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.selectable import Join


class InnerHashJoin(Join):
    """Prefer a hash join on SQL Server; use an ordinary inner join elsewhere."""
    inherit_cache = True


@compiles(InnerHashJoin)
def _default_hash_join(element, compiler, **kwargs):
    return compiler.visit_join(element, **kwargs)


@compiles(InnerHashJoin, "mssql")
def _mssql_hash_join(element, compiler, **kwargs):
    if element.isouter or element.full:
        raise ValueError("InnerHashJoin supports only inner joins.")
    sql = compiler.visit_join(element, **kwargs)
    # Reuse SQLAlchemy's quoting, parameters and FROM correlation. The right
    # relation is a validated table here; do not rewrite nested ACL/JSON joins.
    right = compiler.process(element.right, asfrom=True)
    marker = " JOIN " + right + " ON "
    before, separator, after = sql.rpartition(marker)
    if not separator:
        raise ValueError("Could not compile the scoped SQL Server join.")
    return before + " INNER HASH JOIN " + right + " ON " + after
