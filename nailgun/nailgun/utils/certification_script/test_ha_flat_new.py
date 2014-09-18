@test(groups=["thread_4", "ha"])
class TestHaFlatAddCompute(TestBasic):

    @test(depends_on=[SetupEnvironment.prepare_slaves_5],
          groups=["ha_flat_add_compute"])
    @log_snapshot_on_error
    def ha_flat_add_compute(self):
        """Add compute node to cluster in HA mode with flat nova-network

        Scenario:
            1. Create cluster
            2. Add 3 nodes with controller roles
            3. Add 2 nodes with compute roles
            4. Deploy the cluster
            5. Validate cluster was set up correctly, there are no dead
            services, there are no errors in logs
            6. Add 1 node with compute role
            7. Deploy the cluster
            8. Run network verification
            9. Run OSTF

        Snapshot ha_flat_add_compute

        """
        self.env.revert_snapshot("ready_with_5_slaves")

        with make_cluster("ha_flat") as cluster:
            self.fuel_web.deploy_cluster_wait(cluster_id)
            self.fuel_web.assert_cluster_ready(
                cluster.nodes[0],
                smiles_count=16,
                networks_count=1, timeout=300)

            self.env.bootstrap_nodes(self.env.nodes().slaves[5:6])
            self.fuel_web.update_nodes(
                cluster_id, {'slave-06': ['compute']}, True, False
            )
            self.fuel_web.deploy_cluster_wait(cluster_id)

            self.fuel_web.verify_network(cluster_id)

            self.fuel_web.run_ostf(
                cluster_id=cluster_id,
                test_sets=['ha', 'smoke', 'sanity'])

            self.env.make_snapshot("ha_flat_add_compute")
