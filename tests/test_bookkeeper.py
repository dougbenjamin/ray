import pytest

from raythena.actors.loggingActor import LoggingActor
from raythena.drivers.esdriver import BookKeeper


@pytest.mark.usefixtures("requires_ray")
class TestBookKeeper:

    def test_add_jobs(self, is_eventservice, config, sample_multijobs, njobs):
        logging_actor = LoggingActor.remote(config)
        bookKeeper = BookKeeper(logging_actor, config)
        bookKeeper.add_jobs(sample_multijobs)
        assert len(bookKeeper.jobs) == njobs
        for pandaID in bookKeeper.jobs:
            assert pandaID in sample_multijobs

    def test_assign_job_to_actor(elf, is_eventservice, config, sample_multijobs,
                                 njobs, sample_ranges, nevents):
        logging_actor = LoggingActor.remote(config)
        bookKeeper = BookKeeper(logging_actor, config)
        bookKeeper.add_jobs(sample_multijobs)
        actor_id = "a1"
        if not is_eventservice:
            job = None
            for i in range(njobs):
                job_tmp = bookKeeper.assign_job_to_actor(actor_id)
                if job:
                    assert job['PandaID'] != job_tmp['PandaID']
                job = job_tmp
            assert not bookKeeper.has_jobs_ready()
            assert not bookKeeper.assign_job_to_actor(actor_id)
        else:
            bookKeeper.add_event_ranges(sample_ranges)
            job = None
            for i in range(njobs):
                job_tmp = bookKeeper.assign_job_to_actor(actor_id)
                if job:
                    assert job['PandaID'] == job_tmp['PandaID']
                job = job_tmp
            bookKeeper.fetch_event_ranges(actor_id, nevents)
            assert bookKeeper.assign_job_to_actor(
                actor_id)['PandaID'] != job['PandaID']

    def test_add_event_ranges(self, is_eventservice, config, sample_multijobs,
                              njobs, nevents, sample_ranges):
        if not is_eventservice:
            pytest.skip()

        logging_actor = LoggingActor.remote(config)
        bookKeeper = BookKeeper(logging_actor, config)
        bookKeeper.add_jobs(sample_multijobs)

        assert not bookKeeper.has_jobs_ready()

        for pandaID in sample_multijobs:
            assert not bookKeeper.is_flagged_no_more_events(pandaID)
            assert bookKeeper.n_ready(pandaID) == 0

        bookKeeper.add_event_ranges(sample_ranges)

        assert bookKeeper.has_jobs_ready()
        for pandaID in sample_multijobs:
            assert bookKeeper.n_ready(pandaID) == nevents

        assert bookKeeper.has_jobs_ready()
        for pandaID in sample_multijobs:
            assert bookKeeper.n_ready(pandaID) == nevents

        for pandaID in sample_ranges:
            sample_ranges[pandaID] = []

        bookKeeper.add_event_ranges(sample_ranges)

        for jobID in bookKeeper.jobs:
            assert bookKeeper.is_flagged_no_more_events(jobID)
        assert bookKeeper.has_jobs_ready()

    def test_fetch_event_ranges(self, is_eventservice, config, sample_multijobs,
                                njobs, nevents, sample_ranges):
        if not is_eventservice:
            pytest.skip()
        worker_ids = [f"w_{i}" for i in range(10)]

        logging_actor = LoggingActor.remote(config)
        bookKeeper = BookKeeper(logging_actor, config)
        bookKeeper.add_jobs(sample_multijobs)
        bookKeeper.add_event_ranges(sample_ranges)

        for wid in worker_ids:
            assert not bookKeeper.fetch_event_ranges(wid, 100)

        assigned_workers = worker_ids[:int(len(worker_ids) / 2)]
        for wid in assigned_workers:
            job = bookKeeper.assign_job_to_actor(wid)
            assert job['PandaID'] in sample_multijobs
            ranges = bookKeeper.fetch_event_ranges(
                wid, int(nevents / len(assigned_workers)))
            assert ranges
        assert not bookKeeper.fetch_event_ranges(wid[0], 1)

    def test_process_event_ranges_update(self, is_eventservice, config,
                                         sample_multijobs, njobs, nevents,
                                         sample_ranges, sample_rangeupdate,
                                         sample_failed_rangeupdate):
        if not is_eventservice:
            pytest.skip("No eventservice jobs")

        logging_actor = LoggingActor.remote(config)
        actor_id = "a1"

        bookKeeper = BookKeeper(logging_actor, config)
        bookKeeper.add_jobs(sample_multijobs)
        bookKeeper.add_event_ranges(sample_ranges)

        for i in range(njobs):
            job = bookKeeper.assign_job_to_actor(actor_id)
            _ = bookKeeper.fetch_event_ranges(actor_id, nevents)
            bookKeeper.process_event_ranges_update(actor_id, sample_rangeupdate)
            assert job.event_ranges_queue.nranges_done() == nevents
            assert not bookKeeper.is_flagged_no_more_events(job['PandaID'])

        assert not bookKeeper.assign_job_to_actor(actor_id)

    def test_process_actor_end(self, is_eventservice, config, njobs,
                               sample_multijobs, nevents, sample_ranges):
        if not is_eventservice:
            pytest.skip("No eventservice jobs")

        logging_actor = LoggingActor.remote(config)
        actor_id_1 = "a1"
        actor_id_2 = "a2"

        bookKeeper = BookKeeper(logging_actor, config)
        bookKeeper.add_jobs(sample_multijobs)
        bookKeeper.add_event_ranges(sample_ranges)

        job = bookKeeper.assign_job_to_actor(actor_id_1)
        pandaID = job['PandaID']
        assert bookKeeper.n_ready(pandaID) == nevents

        bookKeeper.process_actor_end(actor_id_1)
        assert bookKeeper.n_ready(pandaID) == nevents

        job = bookKeeper.assign_job_to_actor(actor_id_1)
        job_2 = bookKeeper.assign_job_to_actor(actor_id_2)
        assert job_2['PandaID'] == job['PandaID'] == pandaID

        ranges_1 = bookKeeper.fetch_event_ranges(actor_id_1, nevents)
        assert len(ranges_1) == nevents

        ranges_2 = bookKeeper.fetch_event_ranges(actor_id_2, nevents)
        assert len(ranges_2) == bookKeeper.n_ready(pandaID) == 0
        assert bookKeeper.assign_job_to_actor(actor_id_2)['PandaID'] != pandaID

        bookKeeper.process_actor_end(actor_id_1)
        assert bookKeeper.n_ready(pandaID) == nevents
        assert bookKeeper.assign_job_to_actor(actor_id_1)['PandaID'] == pandaID
