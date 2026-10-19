"""WASAC Smart Water Billing: the API.

    main.py      the app: start-up, guards, routes
    api/         the routes (one file per area) and deps.py (who is asking?)
    core/        settings, security (passwords, tokens), rate limits
    db/          the database connection, table creation, sample data
    models/      the database tables
    schemas/     request and response shapes
    services/    shared jobs: billing (tariff), SMS, audit log
    anomaly/     spotting leaks and wrong readings, the location check, staff review
    vision/      the meter-photo models and pipeline
    utils/       small helpers (phone numbers)
"""
