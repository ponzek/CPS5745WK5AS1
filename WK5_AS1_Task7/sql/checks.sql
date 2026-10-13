SELECT COUNT(*) AS zip_rows,
       COUNT(*) FILTER (WHERE population IS NULL) AS population_missing,
       COUNT(*) FILTER (WHERE density IS NULL) AS density_missing
FROM lab.uszips;
SELECT zip,state_id,county_name,population,density,timezone FROM lab.uszips WHERE zip='00601';
SELECT * FROM lab.import_manifest;
SELECT county_fips, COUNT(*) AS zip_count, SUM(population) AS assigned_population
FROM lab.uszips WHERE state_id IN ('NJ','NY')
GROUP BY county_fips HAVING COUNT(*) >= 3
ORDER BY assigned_population DESC LIMIT 10;
