import os
DATABASE_URL=os.getenv('DATABASE_URL','postgresql+psycopg://frontier:frontier-demo-local@localhost:17714/frontier')
REDIS_URL=os.getenv('REDIS_URL','redis://localhost:6379/0')
JWT_SECRET=os.getenv('JWT_SECRET','local-venue-frontier-change-this-before-hosting')
SEED_DEMO=os.getenv('SEED_DEMO','false').lower()=='true'
