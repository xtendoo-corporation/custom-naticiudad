{
    "name": "Naticiudad - Devoluciones",
    "summary": "Plazo de devolución, vale automático y control de recogidas en días laborables",
    "version": "19.0.1.0.0",
    "category": "Inventory/Sales",
    "author": "Xtendoo",
    "license": "AGPL-3",
    "depends": ["sale_stock", "sale_loyalty", "resource"],
    "data": [
        "security/security.xml",
        "data/loyalty_program_data.xml",
        "data/ir_cron_data.xml",
        "views/res_config_settings_views.xml",
        "views/stock_picking_views.xml",
        "views/stock_return_picking_views.xml",
    ],
    "installable": True,
}
