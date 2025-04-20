
// Word cloud configuration
function createWordCloud(entities) {
    const words = [];
    
    // Convert entities object to word cloud format
    Object.entries(entities).forEach(([category, items]) => {
      items.forEach(item => {
        words.push({
          text: item,
          size: 20 + Math.random() * 30, // Random size between 20-50
          category: category
        });
      });
    });
  
    // Only create word cloud if we have words
    if (words.length === 0) {
      document.getElementById('entityWordCloud').style.display = 'none';
      const container = document.querySelector('.word-cloud-container');
      container.innerHTML = '<p class="text-muted">No entities found in the document.</p>';
      return;
    }
  
    const width = 600;
    const height = 400;
    
    // Clear any existing content
    d3.select("#entityWordCloud").html("");
    
    const svg = d3.select("#entityWordCloud")
      .attr("width", width)
      .attr("height", height);
      
    const layout = d3.layout.cloud()
      .size([width, height])
      .words(words)
      .padding(5)
      .rotate(() => 0)
      .fontSize(d => d.size)
      .on("end", draw);
      
    layout.start();
    
    function draw(words) {
      const colorScale = d3.scaleOrdinal(d3.schemeCategory10);
      
      svg.append("g")
        .attr("transform", `translate(${width/2},${height/2})`)
        .selectAll("text")
        .data(words)
        .enter().append("text")
        .style("font-size", d => `${d.size}px`)
        .style("fill", d => colorScale(d.category))
        .attr("text-anchor", "middle")
        .attr("transform", d => `translate(${d.x},${d.y})rotate(${d.rotate})`)
        .text(d => d.text)
        .append("title")
        .text(d => `${d.text} (${d.category})`);
    }
  }
  