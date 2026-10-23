from bookledger.ui.status_colors import (
    ERROR_COLOR,
    INVENTORY_STATUS_COLORS,
    NEUTRAL_COLOR,
    SUCCESS_COLOR,
    status_message_color,
)


def test_inventory_status_colors_match_the_approved_mapping():
    assert INVENTORY_STATUS_COLORS == {
        "Available": SUCCESS_COLOR,
        "Sold": ERROR_COLOR,
        "Listed": NEUTRAL_COLOR,
        "Not for Sale": NEUTRAL_COLOR,
    }


def test_status_messages_classify_success_failure_and_neutral_information():
    assert status_message_color("Connected — Ready") == SUCCESS_COLOR
    assert status_message_color("Metadata retrieved · Open Library") == SUCCESS_COLOR
    assert status_message_color("Could not save provider settings") == ERROR_COLOR
    assert status_message_color("Scan Failed") == ERROR_COLOR
    assert status_message_color("Not attempted") == NEUTRAL_COLOR
    assert status_message_color("No matching ISBN record") == NEUTRAL_COLOR
    assert status_message_color("Testing a sample lookup…") == NEUTRAL_COLOR
