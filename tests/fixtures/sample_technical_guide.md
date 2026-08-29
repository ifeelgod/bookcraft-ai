# Cloud-Native Systems Architecture: Patterns and Practice

*By Marcus Vance, Principal Solutions Architect*

## Chapter 1: Microservices and Distributed Consensus

Modern distributed architectures decouple processing nodes across independent failure domains. To maintain strong consistency across stateful replicas, protocols like Raft and Paxos establish deterministic leader election.

> **Architecture Tip:** Always configure an odd number of voting replicas (3, 5, or 7) to guarantee unambiguous quorum formation during network partitions.

### Section 1.1: Quorum Math

The minimum quorum size $Q$ for a cluster of $N$ nodes is defined as:
$$Q = \lfloor N/2 \rfloor + 1$$

| Cluster Nodes ($N$) | Quorum Required ($Q$) | Maximum Fault Tolerance ($F$) |
|---|---|---|
| 3 | 2 | 1 node failure |
| 5 | 3 | 2 node failures |
| 7 | 4 | 3 node failures |
| 9 | 5 | 4 node failures |

## Chapter 2: Event-Driven Streaming and Backpressure

When downstream consumers experience load spikes, reactive stream pipelines must signal upstream producers to throttle event emission.

> **Warning:** Unbounded in-memory buffering without backpressure causes out-of-memory crashes under sustained burst workloads.

### Section 2.1: Asynchronous Worker Patterns
Workers pull jobs from transactional message brokers using lease-based acknowledgment tokens. If a worker terminates prematurely, the broker re-queues the message automatically after the visibility timeout expires.
