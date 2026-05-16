CREATE OR REPLACE VIEW drawer_coordinates AS
SELECT
    d.id                                                              AS drawer_id,
    f.asset_id                                                        AS freezer_asset_id,
    l.layer_number,
    r.rack_number,
    d.drawer_number,
    CONCAT(f.asset_id, '-', l.layer_number, '-', r.rack_number, '-', d.drawer_number)
                                                                      AS drawer_coordinate,
    d.reserved,
    d.reserved_reason
FROM drawer d
JOIN rack    r ON d.rack_id    = r.id
JOIN layer   l ON r.layer_id   = l.id
JOIN freezer f ON l.freezer_id = f.id;
