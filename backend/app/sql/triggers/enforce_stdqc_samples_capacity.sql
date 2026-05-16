CREATE TRIGGER enforce_stdqc_samples_capacity
BEFORE INSERT ON stdqc_container
FOR EACH ROW
EXECUTE FUNCTION check_stdqc_container_capacity();
