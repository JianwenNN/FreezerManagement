CREATE TRIGGER enforce_study_samples_capacity
BEFORE INSERT ON study_sample_container
FOR EACH ROW
EXECUTE FUNCTION check_study_sample_container_capacity();
