import { buildMockGraph } from '../../mock/mockGraphData'

describe('buildMockGraph', () => {
  const graph = buildMockGraph('myorg', 'myapp')

  it('produces 10 clusters', () => {
    expect(graph.clusters).toHaveLength(10)
  })

  it('all file nodes reference a valid cluster id', () => {
    const clusterIds = new Set(graph.clusters.map((c) => c.id))
    const fileNodes = graph.nodes.filter((n) => n.type === 'file')
    for (const node of fileNodes) {
      expect(clusterIds).toContain(node.cluster)
    }
  })

  it('all cluster nodes have type "cluster"', () => {
    const clusterNodes = graph.nodes.filter((n) => n.type === 'cluster')
    expect(clusterNodes.length).toBeGreaterThan(0)
    for (const node of clusterNodes) {
      expect(node.type).toBe('cluster')
    }
  })

  it('node ids are unique', () => {
    const ids = graph.nodes.map((n) => n.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('cluster sizes match file count per cluster', () => {
    for (const cluster of graph.clusters) {
      const fileCount = graph.nodes.filter(
        (n) => n.type === 'file' && n.cluster === cluster.id,
      ).length
      expect(cluster.size).toBe(fileCount)
    }
  })

  it('all edge source/target ids exist as node ids (or are reachable via cluster node ids)', () => {
    const nodeIds = new Set(graph.nodes.map((n) => n.id))
    // CONTAINS edges reference clusterNodeId → fileNodeId, both in the nodes array
    for (const edge of graph.edges) {
      expect(nodeIds).toContain(edge.source)
      expect(nodeIds).toContain(edge.target)
    }
  })
})
