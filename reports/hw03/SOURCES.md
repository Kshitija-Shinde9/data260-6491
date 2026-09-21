# SOURCES.md — DATA-260 HW3 domain corpus

**SID4:** 6491 | **DOMAIN_ID:** 3 — Grocery supply and recall notices

**Documents:** 57 | **Total size:** 395,149 bytes (385.9 KB) | **Minimum required:** 200 KB — **met** (193% of minimum)

**Accessed:** 2026-09-18 | **Publisher:** U.S. Food and Drug Administration (fda.gov), public domain

All documents are local snapshots saved as plain text under `data/corpus/`. Byte sizes and SHA-256 hashes for every file are recorded in `CORPUS_MANIFEST.json`.

## How the snapshots were taken

Each page was fetched over HTTPS, the main article body extracted, HTML tags removed (block-level tags became line breaks, inline tags became spaces so sentences stay intact), and the result saved as UTF-8 text. No content was edited, reordered, or summarised.

## Document list

| # | Local file | Bytes | Source URL | Accessed |
|---|---|---|---|---|
| 1 | `about_core_network.txt` | 5,425 | <https://www.fda.gov/food/outbreaks-foodborne-illness/about-core-network> | 2026-09-18 |
| 2 | `alerts_advisories_safety_information.txt` | 16,990 | <https://www.fda.gov/food/recalls-outbreaks-emergencies/alerts-advisories-safety-information> | 2026-09-18 |
| 3 | `ap_creations_llc_issues_nationwide_recall_biq_fel_due_undeclared_silde.txt` | 3,260 | <https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/ap-creations-llc-issues-nationwide-recall-biq-fel-due-undeclared-sildenafil-and-tadalafil> | 2026-09-18 |
| 4 | `ap_creations_llc_issues_nationwide_recall_x10_natural_enhancement_supp.txt` | 3,692 | <https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/ap-creations-llc-issues-nationwide-recall-x10-natural-enhancement-supplement-due-undeclared> | 2026-09-18 |
| 5 | `bmc_medical_co_ltd_recalls_luna_g3_apap_model_lg3600_firmware_g3_20076.txt` | 4,604 | <https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/bmc-medical-co-ltd-recalls-luna-g3-apap-model-lg3600-firmware-g3-20076-due-firmware-defect> | 2026-09-18 |
| 6 | `buy_store_serve_safe_food.txt` | 2,990 | <https://www.fda.gov/food/consumers/buy-store-serve-safe-food> | 2026-09-18 |
| 7 | `centric_compounding_issues_nationwide_recall_glutathione_myers_cocktai.txt` | 3,331 | <https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/centric-compounding-issues-nationwide-recall-glutathione-myers-cocktail-and-tri-immune-boost-due> | 2026-09-18 |
| 8 | `core_publications.txt` | 24,723 | <https://www.fda.gov/food/outbreaks-foodborne-illness/core-publications> | 2026-09-18 |
| 9 | `evergreen_fresh_sprouts_llc_recalls_broccoli_sprouts_because_possible_.txt` | 2,582 | <https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/evergreen-fresh-sprouts-llc-recalls-broccoli-sprouts-because-possible-health-risk> | 2026-09-18 |
| 10 | `fda_advises_consumers_and_retailers_not_eat_serve_or_sell_certain_impe.txt` | 3,790 | <https://www.fda.gov/food/alerts-advisories-safety-information/fda-advises-consumers-and-retailers-not-eat-serve-or-sell-certain-imperial-brand-cookies-and-candies> | 2026-09-18 |
| 11 | `fda_advises_consumers_not_inhale_nitrous_oxide_products.txt` | 3,452 | <https://www.fda.gov/food/alerts-advisories-safety-information/fda-advises-consumers-not-inhale-nitrous-oxide-products> | 2026-09-18 |
| 12 | `fda_advises_consumers_not_use_fulvic_care_powder_and_tablets_black_oxy.txt` | 3,398 | <https://www.fda.gov/food/alerts-advisories-safety-information/fda-advises-consumers-not-use-fulvic-care-powder-and-tablets-black-oxygen-organics-due-elevated> | 2026-09-18 |
| 13 | `fda_advises_consumers_retailers_and_distributors_not_eat_sell_or_distr.txt` | 4,248 | <https://www.fda.gov/food/alerts-advisories-safety-information/fda-advises-consumers-retailers-and-distributors-not-eat-sell-or-distribute-addall-xr-shot-or-addall> | 2026-09-18 |
| 14 | `fda_advises_consumers_retailers_and_distributors_not_eat_sell_or_serve.txt` | 5,681 | <https://www.fda.gov/food/alerts-advisories-safety-information/fda-advises-consumers-retailers-and-distributors-not-eat-sell-or-serve-recalled-black-sheep-egg> | 2026-09-18 |
| 15 | `fda_advises_consumers_retailers_and_distributors_not_use_eat_sell_or_s.txt` | 11,231 | <https://www.fda.gov/food/alerts-advisories-safety-information/fda-advises-consumers-retailers-and-distributors-not-use-eat-sell-or-serve-products-pan-african-food> | 2026-09-18 |
| 16 | `fda_advises_parents_and_caregivers_not_buy_or_feed_wanabana_apple_cinn.txt` | 4,311 | <https://www.fda.gov/food/alerts-advisories-safety-information/fda-advises-parents-and-caregivers-not-buy-or-feed-wanabana-apple-cinnamon-fruit-puree-pouches> | 2026-09-18 |
| 17 | `fda_advises_public_not_eat_sell_or_serve_certain_imported_frozen_shrim.txt` | 12,114 | <https://www.fda.gov/food/alerts-advisories-safety-information/fda-advises-public-not-eat-sell-or-serve-certain-imported-frozen-shrimp-indonesian-firm> | 2026-09-18 |
| 18 | `fda_advises_restaurants_and_retailers_not_serve_or_sell_and_consumers_.txt` | 4,372 | <https://www.fda.gov/food/alerts-advisories-safety-information/fda-advises-restaurants-and-retailers-not-serve-or-sell-and-consumers-not-eat-product-labeled-sun> | 2026-09-18 |
| 19 | `fda_alert_concerning_certain_cinnamon_products_due_presence_elevated_l.txt` | 8,851 | <https://www.fda.gov/food/alerts-advisories-safety-information/fda-alert-concerning-certain-cinnamon-products-due-presence-elevated-levels-lead> | 2026-09-18 |
| 20 | `fda_alerts_parents_and_caregivers_cronobacter_safety_concerns_crecelac.txt` | 5,526 | <https://www.fda.gov/food/alerts-advisories-safety-information/fda-alerts-parents-and-caregivers-cronobacter-safety-concerns-crecelac-goat-milk-infant-formula> | 2026-09-18 |
| 21 | `fda_calls_food_industry_leaders_strengthen_recall_compliance_and_ensur.txt` | 9,807 | <https://www.fda.gov/food/recalls-outbreaks-emergencies/fda-calls-food-industry-leaders-strengthen-recall-compliance-and-ensure-recall-effectiveness> | 2026-09-18 |
| 22 | `fda_encourages_food_industry_leaders_streamline_enhance_product_recall.txt` | 4,921 | <https://www.fda.gov/food/recalls-outbreaks-emergencies/fda-encourages-food-industry-leaders-streamline-enhance-product-recall-communications-public-and> | 2026-09-18 |
| 23 | `fda_expands_warning_consumers_about_toxic_yellow_oleander_purported_be.txt` | 7,451 | <https://www.fda.gov/food/alerts-advisories-safety-information/fda-expands-warning-consumers-about-toxic-yellow-oleander-purported-be-nuez-de-la-india-certain> | 2026-09-18 |
| 24 | `fda_issues_warning_about_certain_products_containing_toxic_yellow_olea.txt` | 10,471 | <https://www.fda.gov/food/alerts-advisories-safety-information/fda-issues-warning-about-certain-products-containing-toxic-yellow-oleander> | 2026-09-18 |
| 25 | `fda_issues_warning_about_imported_cookware_may_leach_lead_august_2025.txt` | 9,767 | <https://www.fda.gov/food/alerts-advisories-safety-information/fda-issues-warning-about-imported-cookware-may-leach-lead-august-2025> | 2026-09-18 |
| 26 | `fda_issues_warning_about_toxic_amygdalin_found_apricot_seeds.txt` | 3,486 | <https://www.fda.gov/food/alerts-advisories-safety-information/fda-issues-warning-about-toxic-amygdalin-found-apricot-seeds> | 2026-09-18 |
| 27 | `fda_issues_warning_letter_bimbo_bakeries_over_food_allergen_labeling_c.txt` | 4,095 | <https://www.fda.gov/food/hfp-constituent-updates/fda-issues-warning-letter-bimbo-bakeries-over-food-allergen-labeling-concerns> | 2026-09-18 |
| 28 | `fda_issues_warning_letter_manufacturer_apple_cinnamon_fruit_puree_prod.txt` | 5,113 | <https://www.fda.gov/food/hfp-constituent-updates/fda-issues-warning-letter-manufacturer-apple-cinnamon-fruit-puree-products-containing-elevated> | 2026-09-18 |
| 29 | `fda_public_health_alert_additional_ground_cinnamon_product_due_presenc.txt` | 8,853 | <https://www.fda.gov/food/alerts-advisories-safety-information/fda-public-health-alert-additional-ground-cinnamon-product-due-presence-elevated-levels-lead> | 2026-09-18 |
| 30 | `fda_warns_consumers_about_accidental_ingestion_children_food_products_.txt` | 4,216 | <https://www.fda.gov/food/alerts-advisories-safety-information/fda-warns-consumers-about-accidental-ingestion-children-food-products-containing-thc> | 2026-09-18 |
| 31 | `fda_warns_consumers_not_use_optimized_plant_mediated_solutions_opms_bl.txt` | 3,138 | <https://www.fda.gov/food/alerts-advisories-safety-information/fda-warns-consumers-not-use-optimized-plant-mediated-solutions-opms-black-liquid-kratom> | 2026-09-18 |
| 32 | `food_and_water_safety_during_power_outages_and_floods.txt` | 10,556 | <https://www.fda.gov/food/buy-store-serve-safe-food/food-and-water-safety-during-power-outages-and-floods> | 2026-09-18 |
| 33 | `food_safety_tips_consumers_retailers_during_outbreak_foodborne_illness.txt` | 3,671 | <https://www.fda.gov/food/outbreaks-foodborne-illness/food-safety-tips-consumers-retailers-during-outbreak-foodborne-illness> | 2026-09-18 |
| 34 | `foodborne_illness_outbreak_executive_incident_summary_abstracts.txt` | 5,561 | <https://www.fda.gov/food/outbreaks-foodborne-illness/foodborne-illness-outbreak-executive-incident-summary-abstracts> | 2026-09-18 |
| 35 | `foodborne_outbreak_response_improvement_plan.txt` | 25,427 | <https://www.fda.gov/food/outbreaks-foodborne-illness/foodborne-outbreak-response-improvement-plan> | 2026-09-18 |
| 36 | `foodborne_pathogens.txt` | 3,827 | <https://www.fda.gov/food/outbreaks-foodborne-illness/foodborne-pathogens> | 2026-09-18 |
| 37 | `freshpoint_issues_recall_due_improperly_declared_allergen_egg_chicken_.txt` | 2,004 | <https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/freshpoint-issues-recall-due-improperly-declared-allergen-egg-chicken-salad-wedge-sandwiches> | 2026-09-18 |
| 38 | `get_assistance_fda_human_foods_program_hfp.txt` | 9,413 | <https://www.fda.gov/food/resources-you-food/get-assistance-fda-human-foods-program-hfp> | 2026-09-18 |
| 39 | `gf_blends_recalls_truly_aip_all_purpose_flour_and_bread_mix_and_eat_ga.txt` | 2,865 | <https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/gf-blends-recalls-truly-aip-all-purpose-flour-and-bread-mix-and-eat-gangster-flat-bread-pizza-mix> | 2026-09-18 |
| 40 | `gias_foods_inc_recalls_bettergoods_authentic_italian_lemon_alfredo_fet.txt` | 2,468 | <https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/gias-foods-inc-recalls-bettergoods-authentic-italian-lemon-alfredo-fettuccine-because-possible> | 2026-09-18 |
| 41 | `industry_and_consumer_assistance_food_dietary_supplements_and_cosmetic.txt` | 9,413 | <https://www.fda.gov/food/resources-you/industry-and-consumer-assistance-food-dietary-supplements-and-cosmetics> | 2026-09-18 |
| 42 | `investigations_foodborne_illness_outbreaks.txt` | 26,973 | <https://www.fda.gov/food/outbreaks-foodborne-illness/investigations-foodborne-illness-outbreaks> | 2026-09-18 |
| 43 | `more_ground_cinnamon_products_added_fda_public_health_alert_due_presen.txt` | 15,555 | <https://www.fda.gov/food/alerts-advisories-safety-information/more-ground-cinnamon-products-added-fda-public-health-alert-due-presence-elevated-levels-lead> | 2026-09-18 |
| 44 | `people_risk_foodborne_illness.txt` | 5,532 | <https://www.fda.gov/food/consumers/people-risk-foodborne-illness> | 2026-09-18 |
| 45 | `post_outbreak_response_and_prevention_strategies_enhance_food_safety_u.txt` | 7,075 | <https://www.fda.gov/food/outbreaks-foodborne-illness/post-outbreak-response-and-prevention-strategies-enhance-food-safety-updated-january-17-2025> | 2026-09-18 |
| 46 | `public_health_advisories_investigations_foodborne_illness_outbreaks.txt` | 6,667 | <https://www.fda.gov/food/outbreaks-foodborne-illness/public-health-advisories-investigations-foodborne-illness-outbreaks> | 2026-09-18 |
| 47 | `public_health_alert_concerning_possible_listeria_contamination_felix_c.txt` | 5,214 | <https://www.fda.gov/food/alerts-advisories-safety-information/public-health-alert-concerning-possible-listeria-contamination-felix-custom-smoking-seafood-products> | 2026-09-18 |
| 48 | `public_health_alert_concerning_possible_listeria_contamination_little_.txt` | 3,814 | <https://www.fda.gov/food/alerts-advisories-safety-information/public-health-alert-concerning-possible-listeria-contamination-little-hatchs-ready-eat-foods> | 2026-09-18 |
| 49 | `public_health_alert_concerning_recalled_everest_and_maggi_brand_spices.txt` | 3,608 | <https://www.fda.gov/food/alerts-advisories-safety-information/public-health-alert-concerning-recalled-everest-and-maggi-brand-spices-because-possible-health-risk> | 2026-09-18 |
| 50 | `refrigerator_thermometers_cold_facts_about_food_safety.txt` | 10,305 | <https://www.fda.gov/food/buy-store-serve-safe-food/refrigerator-thermometers-cold-facts-about-food-safety> | 2026-09-18 |
| 51 | `safe_food_handling.txt` | 5,086 | <https://www.fda.gov/food/buy-store-serve-safe-food/safe-food-handling> | 2026-09-18 |
| 52 | `saratoga_potato_chips_issues_allergy_alert_undeclared_soy_j_higgs_load.txt` | 1,954 | <https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/saratoga-potato-chips-issues-allergy-alert-undeclared-soy-j-higgs-loaded-bacon-and-cheddar-potato> | 2026-09-18 |
| 53 | `so_delicious_dairy_freer_issues_voluntary_recall_salted_caramel_cluste.txt` | 2,600 | <https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/so-delicious-dairy-freer-issues-voluntary-recall-salted-caramel-cluster-non-dairy-frozen-dessert> | 2026-09-18 |
| 54 | `strengthening_food_safety_through_root_cause_analysis.txt` | 5,459 | <https://www.fda.gov/food/outbreaks-foodborne-illness/strengthening-food-safety-through-root-cause-analysis> | 2026-09-18 |
| 55 | `what_you_need_know_about_foodborne_illnesses.txt` | 5,912 | <https://www.fda.gov/food/consumers/what-you-need-know-about-foodborne-illnesses> | 2026-09-18 |
| 56 | `what_you_need_know_about_preventing_listeria_infections.txt` | 5,987 | <https://www.fda.gov/food/buy-store-serve-safe-food/what-you-need-know-about-preventing-listeria-infections> | 2026-09-18 |
| 57 | `whole_foods_market_issues_allergy_alert_undeclared_egg_cabricharme_che.txt` | 2,314 | <https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/whole-foods-market-issues-allergy-alert-undeclared-egg-cabricharme-cheese> | 2026-09-18 |
