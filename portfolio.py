"""Portfolio ranking and lookup utilities."""
from data_loader import load_dataset


def get_portfolio_rank_and_size(object_id):
    """Get object rank and total portfolio size by annual cost, without rebuilding full bootstrap."""
    data = load_dataset()
    objects = data["objects"]
    
    # Build lightweight portfolio with only rank-determining fields
    portfolio = sorted(
        [
            {
                "id": item["id"],
                "annualCost": item["summary"]["totalCost"],
            }
            for item in objects
        ],
        key=lambda entry: entry["annualCost"],
        reverse=True,
    )
    
    rank = next((index + 1 for index, item in enumerate(portfolio) if item["id"] == object_id), None)
    return rank, len(portfolio)
