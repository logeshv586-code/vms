// Canvas animation for login page
export const initializeLoginAnimation = (canvasRef) => {
  if (!canvasRef.current) return;
  
  const canvas = canvasRef.current;
  const ctx = canvas.getContext('2d');
  
  // Set canvas dimensions
  const resizeCanvas = () => {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  };
  
  resizeCanvas();
  window.addEventListener('resize', resizeCanvas);
  
  // Shape data
  const shapePathData = [
    'M231,352l445-156L600,0L452,54L331,3L0,48L231,352',
    'M0,0l64,219L29,343l535,30L478,37l-133,4L0,0z',
    'M0,65l16,138l96,107l270-2L470,0L337,4L0,65z',
    'M333,0L0,94l64,219L29,437l570-151l-196-42L333,0',
    'M331.9,3.6l-331,45l231,304l445-156l-76-196l-148,54L331.9,3.6z',
    'M389,352l92-113l195-43l0,0l0,0L445,48l-80,1L122.7,0L0,275.2L162,297L389,352',
    'M 50 100 L 300 150 L 550 50 L 750 300 L 500 250 L 300 450 L 50 100',
    'M 700 350 L 500 350 L 700 500 L 400 400 L 200 450 L 250 350 L 100 300 L 150 50 L 350 100 L 250 150 L 450 150 L 400 50 L 550 150 L 350 250 L 650 150 L 650 50 L 700 150 L 600 250 L 750 250 L 650 300 L 700 350 '
  ];
  
  // Calculate positions
  const getPositions = () => {
    const canvasWidth = canvas.width;
    const canvasHeight = canvas.height;
    const canvasMiddleX = canvasWidth / 2;
    const canvasMiddleY = canvasHeight / 2;
    
    return [
      { x: (canvasMiddleX / 2) + 100, y: 100 },
      { x: 200, y: canvasMiddleY },
      { x: (canvasMiddleX - 50) + (canvasMiddleX / 2), y: 150 },
      { x: 0, y: canvasMiddleY + 100 },
      { x: canvasWidth - 130, y: canvasHeight - 75 },
      { x: canvasMiddleX + 80, y: canvasHeight - 50 },
      { x: canvasWidth + 60, y: canvasMiddleY - 50 },
      { x: canvasMiddleX + 100, y: canvasMiddleY + 100 }
    ];
  };
  
  // Create shapes
  let shapes = [];
  
  const initializeShapes = () => {
    const positions = getPositions();
    shapes = [];
    
    for (let i = 0; i < shapePathData.length && i < positions.length; i++) {
      const path = new Path2D(shapePathData[i]);
      shapes.push({
        path,
        position: positions[i],
        rotation: 0,
        direction: i % 2 === 0 ? -1 : 1,
        scale: 2
      });
    }
  };
  
  // Animation loop
  let frameCount = 0;
  const animate = () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    frameCount++;
    if (frameCount % 4 === 0) {
      // Update rotation
      shapes.forEach(shape => {
        shape.rotation += 0.1 * shape.direction;
      });
    }
    
    // Draw shapes
    shapes.forEach(shape => {
      ctx.save();
      ctx.translate(shape.position.x, shape.position.y);
      ctx.rotate(shape.rotation);
      ctx.scale(shape.scale, shape.scale);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
      ctx.lineWidth = 1 / shape.scale;
      ctx.stroke(shape.path);
      ctx.restore();
    });
    
    requestAnimationFrame(animate);
  };
  
  // Initialize and start animation
  initializeShapes();
  animate();
  
  // Clean up function
  return () => {
    window.removeEventListener('resize', resizeCanvas);
  };
};

// Toggle between sign up and login
export const initializeToggle = () => {
  document.getElementById('goRight')?.addEventListener('click', () => {
    document.getElementById('slideBox').style.marginLeft = '0';
    document.querySelector('.topLayer').style.marginLeft = '100%';
  });
  
  document.getElementById('goLeft')?.addEventListener('click', () => {
    if (window.innerWidth > 769) {
      document.getElementById('slideBox').style.marginLeft = '50%';
    } else {
      document.getElementById('slideBox').style.marginLeft = '20%';
    }
    document.querySelector('.topLayer').style.marginLeft = '0';
  });
};
