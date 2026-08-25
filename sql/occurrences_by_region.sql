-- Resolved mineral occurrences (deduplicated across reports of the same
-- site), grouped into a coarse region grid for a "by region" summary.
SELECT
    mineral,
    ROUND(lat_bucket, 0) AS region_lat,
    ROUND(lon_bucket, 0) AS region_lon,
    COUNT(*) AS n_occurrences,
    SUM(n_reports) AS n_source_reports,
    ROUND(AVG(avg_depth_m), 1) AS avg_depth_m,
    ROUND(AVG(avg_grade_g_t), 2) AS avg_grade_g_t
FROM occurrences
GROUP BY mineral, region_lat, region_lon
ORDER BY n_occurrences DESC;
