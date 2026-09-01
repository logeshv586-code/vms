import React, { useState, useEffect } from 'react';

const PanelIcon = () => (
  <svg
    width="18"
    height="18"
    viewBox="0 0 20 20"
    fill="currentColor"
    xmlns="http://www.w3.org/2000/svg"
    className="max-md:hidden"
    style={{ filter: 'drop-shadow(0 1px 1px rgba(0, 0, 0, 0.1))' }}
  >
    <path d="M6.83496 3.99992C6.38353 4.00411 6.01421 4.0122 5.69824 4.03801C5.31232 4.06954 5.03904 4.12266 4.82227 4.20012L4.62207 4.28606C4.18264 4.50996 3.81498 4.85035 3.55859 5.26848L3.45605 5.45207C3.33013 5.69922 3.25006 6.01354 3.20801 6.52824C3.16533 7.05065 3.16504 7.71885 3.16504 8.66301V11.3271C3.16504 12.2712 3.16533 12.9394 3.20801 13.4618C3.25006 13.9766 3.33013 14.2909 3.45605 14.538L3.55859 14.7216C3.81498 15.1397 4.18266 15.4801 4.62207 15.704L4.82227 15.79C5.03904 15.8674 5.31234 15.9205 5.69824 15.9521C6.01398 15.9779 6.383 15.986 6.83398 15.9902L6.83496 3.99992ZM18.165 11.3271C18.165 12.2493 18.1653 12.9811 18.1172 13.5702C18.0745 14.0924 17.9916 14.5472 17.8125 14.9648L17.7295 15.1415C17.394 15.8 16.8834 16.3511 16.2568 16.7353L15.9814 16.8896C15.5157 17.1268 15.0069 17.2285 14.4102 17.2773C13.821 17.3254 13.0893 17.3251 12.167 17.3251H7.83301C6.91071 17.3251 6.17898 17.3254 5.58984 17.2773C5.06757 17.2346 4.61294 17.1508 4.19531 16.9716L4.01855 16.8896C3.36014 16.5541 2.80898 16.0434 2.4248 15.4169L2.27051 15.1415C2.03328 14.6758 1.93158 14.167 1.88281 13.5702C1.83468 12.9811 1.83496 12.2493 1.83496 11.3271V8.66301C1.83496 7.74072 1.83468 7.00898 1.88281 6.41985C1.93157 5.82309 2.03329 5.31432 2.27051 4.84856L2.4248 4.57317C2.80898 3.94666 3.36012 3.436 4.01855 3.10051L4.19531 3.0175C4.61285 2.83843 5.06771 2.75548 5.58984 2.71281C6.17898 2.66468 6.91071 2.66496 7.83301 2.66496H12.167C13.0893 2.66496 13.821 2.66468 14.4102 2.71281C15.0069 2.76157 15.5157 2.86329 15.9814 3.10051L16.2568 3.25481C16.8833 3.63898 17.394 4.19012 17.7295 4.84856L17.8125 5.02531C17.9916 5.44285 18.0745 5.89771 18.1172 6.41985C18.1653 7.00898 18.165 7.74072 18.165 8.66301V11.3271ZM8.16406 15.995H12.167C13.1112 15.995 13.7794 15.9947 14.3018 15.9521C14.8164 15.91 15.1308 15.8299 15.3779 15.704L15.5615 15.6015C15.9797 15.3451 16.32 14.9774 16.5439 14.538L16.6299 14.3378C16.7074 14.121 16.7605 13.8478 16.792 13.4618C16.8347 12.9394 16.835 12.2712 16.835 11.3271V8.66301C16.835 7.71885 16.8347 7.05065 16.792 6.52824C16.7605 6.14232 16.7073 5.86904 16.6299 5.65227L16.5439 5.45207C16.32 5.01264 15.9796 4.64498 15.5615 4.3886L15.3779 4.28606C15.1308 4.16013 14.8165 4.08006 14.3018 4.03801C13.7794 3.99533 13.1112 3.99504 12.167 3.99504H8.16406C8.16407 3.99667 8.16504 3.99829 8.16504 3.99992L8.16406 15.995Z"/>
  </svg>
);

const CloseIcon = () => (
  <svg
    width="18"
    height="18"
    viewBox="0 0 20 20"
    fill="currentColor"
    xmlns="http://www.w3.org/2000/svg"
    className="md:hidden"
    style={{ filter: 'drop-shadow(0 1px 1px rgba(0, 0, 0, 0.1))' }}
  >
    <path d="M14.2548 4.75488C14.5282 4.48152 14.9717 4.48152 15.2451 4.75488C15.5184 5.02825 15.5184 5.47175 15.2451 5.74512L10.9902 10L15.2451 14.2549L15.3349 14.3652C15.514 14.6369 15.4841 15.006 15.2451 15.2451C15.006 15.4842 14.6368 15.5141 14.3652 15.335L14.2548 15.2451L9.99995 10.9902L5.74506 15.2451C5.4717 15.5185 5.0282 15.5185 4.75483 15.2451C4.48146 14.9718 4.48146 14.5282 4.75483 14.2549L9.00971 10L4.75483 5.74512L4.66499 5.63477C4.48589 5.3631 4.51575 4.99396 4.75483 4.75488C4.99391 4.51581 5.36305 4.48594 5.63471 4.66504L5.74506 4.75488L9.99995 9.00977L14.2548 4.75488Z"/>
  </svg>
);

const SidebarToggleButton = ({ onClick, ariaExpanded }) => {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768); // md breakpoint
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);
   
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  const buttonStyles = {
    height: isMobile ? '40px' : '36px',
    width: isMobile ? '40px' : '36px',
    borderRadius: '8px',
    backgroundColor: '#132447f0',
    border: '1px solid #1e3a5f',
    color: '#e5e7eb',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'all 0.2s ease',
    boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06)',
    position: 'relative',
    transform: 'translateY(0px)',
    marginLeft: 'auto',
    marginRight: '8px',
  };

  const handleMouseOver = (e) => {
    e.target.style.backgroundColor = '#132447';
    e.target.style.borderColor = '#2a4a6b';
    e.target.style.color = '#f9fafb';
    e.target.style.transform = 'translateY(-1px)';
    e.target.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.15), 0 2px 4px rgba(0, 0, 0, 0.1)';
  };

  const handleMouseOut = (e) => {
    e.target.style.backgroundColor = '#132447f0';
    e.target.style.borderColor = '#1e3a5f';
    e.target.style.color = '#e5e7eb';
    e.target.style.transform = 'translateY(0px)';
    e.target.style.boxShadow = '0 2px 4px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06)';
  };

  const handleMouseDown = (e) => {
    e.target.style.transform = 'translateY(1px)';
    e.target.style.boxShadow = '0 1px 2px rgba(0, 0, 0, 0.1)';
  };

  const handleMouseUp = (e) => {
    e.target.style.transform = 'translateY(-1px)';
    e.target.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.15), 0 2px 4px rgba(0, 0, 0, 0.1)';
  };

  const handleFocus = (e) => {
    e.target.style.backgroundColor = '#132447';
    e.target.style.borderColor = '#2a4a6b';
    e.target.style.color = '#f9fafb';
    e.target.style.outline = '2px solid #3b82f6';
    e.target.style.outlineOffset = '2px';
  };

  const handleBlur = (e) => {
    e.target.style.backgroundColor = '#132447f0';
    e.target.style.borderColor = '#1e3a5f';
    e.target.style.color = '#e5e7eb';
    e.target.style.outline = 'none';
    e.target.style.outlineOffset = '0px';
  };

  return (
    <button
      onClick={onClick}
      aria-expanded={ariaExpanded}
      aria-controls="stage-slideover-sidebar"
      aria-label="Toggle sidebar"
      data-testid="sidebar-toggle-button"
      style={buttonStyles}
      onMouseOver={handleMouseOver}
      onMouseOut={handleMouseOut}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      onFocus={handleFocus}
      onBlur={handleBlur}
    >
      {isMobile ? <CloseIcon /> : <PanelIcon />}
    </button>
  );
};

export default SidebarToggleButton;
