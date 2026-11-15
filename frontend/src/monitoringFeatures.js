export const featureMeta = name => {
  const group = /flow|inbound_|outbound_count|recency_months/.test(name) && !/failure|processing/.test(name) ? 'Flow volume'
    : /failure|processing|friction/.test(name) ? 'Payment failures'
    : /session|login|users|device|approver/.test(name) ? 'Digital activity'
    : /balance|account|fd_|fee|waiver|offer/.test(name) ? 'Balances' : 'Customer profile';
  const unit = name.endsWith('_myr') ? 'money'
    : /_ratio_/.test(name) ? 'ratio'
    : /_rate(?:_|$)|_share_|_pct$/.test(name) ? 'fraction'
    : /_change_|_cv_/.test(name) ? 'decimal'
    : /_days$/.test(name) ? 'days'
    : /_months$/.test(name) ? 'months'
    : /_sec$/.test(name) ? 'seconds'
    : /_ms$/.test(name) ? 'milliseconds'
    : /count|users|transactions|retries|zero_months/.test(name) ? 'count'
    : ['tier_id','customer_type','sector_code'].includes(name) ? 'category' : 'saved units';
  const labels = {
    combined_flow_mean_3m_myr:'Combined flow, 3-month mean',
    combined_flow_mean_12m_myr:'Combined flow, 12-month mean',
    login_failure_rate_3m:'Login failure rate, 3 months',
    outbound_failure_rate_3m:'Outgoing payment failure rate, 3 months',
    non_fd_balance_myr:'Operating account balance',
    fd_balance_myr:'Fixed deposit balance',
    tier_id:'Customer tier mix',customer_type:'Customer type mix',sector_code:'Sector mix',
  };
  const label = labels[name] || name.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
  return {group,label,unit};
};

export const curatedFeatures = ['combined_flow_mean_3m_myr','combined_flow_mean_12m_myr',
  'login_failure_rate_3m','outbound_failure_rate_3m','non_fd_balance_myr','fd_balance_myr',
  'tier_id','customer_type','sector_code'];
