from interface.vendors.management.commands.sync_marketplace_listings import Command as SyncMarketplaceListingsCommand


class Command(SyncMarketplaceListingsCommand):
    help = "Deprecated alias for sync_marketplace_listings."
